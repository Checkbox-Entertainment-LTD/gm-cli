import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from commit_policy import classify, pushed_commits


class CommitPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'ci@example.invalid')
        self.git('config', 'user.name', 'CI test')
        (self.root / 'ci').mkdir()
        (self.root / 'ci/runner-lock.json').write_text('{"runtime":"2024.14.4.268"}')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True).strip()

    def commit(self, version, code='old'):
        (self.root / 'ci/release-version.txt').write_text(version + '\n')
        (self.root / 'source.cpp').write_text(code)
        self.git('add', '.')
        self.git('commit', '-qm', 'change')
        return self.git('rev-parse', 'HEAD')

    def test_runner_bump_and_source_same_commit_then_later_changes(self):
        self.commit('2024.14.4.268-c1')
        release = self.commit('2024.14.4.268-c2', 'fifty fixes')
        later = self.commit('2024.14.4.268-c2', 'not released yet')
        result = classify(self.root, release, 'runner')
        self.assertTrue(result['release'])
        self.assertEqual(result['commit'], release)
        self.assertEqual(self.git('show', result['commit'] + ':source.cpp'), 'fifty fixes')
        self.assertFalse(classify(self.root, later, 'runner')['release'])

    def test_cli_bump_and_source_same_commit(self):
        self.commit('2.3.0-checkbox.1')
        sha = self.commit('2.3.0-checkbox.2', 'PS4')
        result = classify(self.root, sha, 'cli')
        self.assertTrue(result['release'])
        self.assertEqual(self.git('show', result['commit'] + ':source.cpp'), 'PS4')

    def test_first_version_only_validates_and_whitespace_is_not_bump(self):
        sha = self.commit('2024.14.4.268-c1')
        self.assertFalse(classify(self.root, sha, 'runner')['release'])
        sha = self.commit('2024.14.4.268-c1\n')
        self.assertFalse(classify(self.root, sha, 'runner')['release'])

    def test_decrease_and_base_mismatch_rejected(self):
        self.commit('2024.14.4.268-c2')
        sha = self.commit('2024.14.4.268-c1')
        with self.assertRaises(ValueError): classify(self.root, sha, 'runner')
        sha = self.commit('2024.14.5.300-c1')
        with self.assertRaises(ValueError): classify(self.root, sha, 'runner')

    def test_multicommit_push_enumerates_bump_and_following_commit(self):
        before = self.commit('2024.14.4.268-c1')
        bump = self.commit('2024.14.4.268-c2', 'fix')
        after = self.commit('2024.14.4.268-c2', 'next')
        self.git('remote', 'add', 'origin', str(self.root))
        self.assertEqual(pushed_commits(self.root, {'before': before, 'after': after,
                         'ref': 'refs/heads/anything'}), [bump, after])

    def test_merge_uses_first_parent(self):
        base = self.commit('2024.14.4.268-c1')
        self.git('checkout', '-qb', 'arbitrary')
        self.commit('2024.14.4.268-c2', 'fix')
        self.git('checkout', '--detach', base)
        self.git('merge', '--no-ff', '-m', 'merge', 'arbitrary')
        sha = self.git('rev-parse', 'HEAD')
        self.assertTrue(classify(self.root, sha, 'runner')['release'])


if __name__ == '__main__': unittest.main()
