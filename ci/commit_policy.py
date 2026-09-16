#!/usr/bin/env python3
"""Classify the exact commit, never the branch tip, for validation/publication."""
import argparse
import json
from pathlib import Path
import re
import subprocess


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def parse_version(value, kind):
    pattern = r'(\d+)\.(\d+)\.(\d+)\.(\d+)-c([1-9]\d*)' if kind == 'runner' else r'(\d+)\.(\d+)\.(\d+)-checkbox\.([1-9]\d*)'
    match = re.fullmatch(pattern, value)
    if not match or any(str(int(x)) != x for x in match.groups()):
        raise ValueError('Invalid canonical ' + kind + ' version: ' + value)
    return tuple(map(int, match.groups()))


def classify(root, commit, kind):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Source must be a full commit SHA')
    path = 'ci/release-version.txt'
    current = git(root, 'show', commit + ':' + path)
    parsed = parse_version(current, kind)
    parents = git(root, 'rev-list', '--parents', '-n', '1', commit).split()[1:]
    previous = None
    if parents:
        exists = subprocess.run(['git', '-C', str(root), 'cat-file', '-e', parents[0] + ':' + path],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if exists:
            previous = git(root, 'show', parents[0] + ':' + path)
    # Introducing CI/version tracking is validation only, not an accidental release.
    release = previous is not None and current != previous
    if release and parsed <= parse_version(previous, kind):
        raise ValueError('A release version must increase relative to the first parent')
    if kind == 'runner':
        lock = json.loads(git(root, 'show', commit + ':ci/runner-lock.json'))
        if current.split('-c')[0] != lock['runtime']:
            raise ValueError('Version does not match the pinned official base')
    return {'schema': 1, 'kind': kind, 'commit': commit, 'version': current,
            'previous': previous, 'release': release,
            'identity': current if release else current + '-dev.' + commit}


def pushed_commits(root, event):
    if event.get('deleted') or not event.get('ref', '').startswith('refs/heads/'):
        return []
    before, after = event['before'], event['after']
    if not all(re.fullmatch(r'[0-9a-f]{40}', x) for x in [before, after]):
        raise ValueError('Invalid event commit')
    if before != '0' * 40:
        # Force pushes are a graph difference too. Never truncate to the push tip.
        git(root, 'fetch', '--no-tags', 'origin', before)
        return git(root, 'rev-list', '--reverse', '--topo-order', after, '^' + before).splitlines()
    others = git(root, 'for-each-ref', '--format=%(objectname) %(refname)', 'refs/remotes/origin').splitlines()
    excluded = [line.split()[0] for line in others
                if line.split()[1] not in ('refs/remotes/origin/HEAD',
                                          'refs/remotes/origin/' + event['ref'][11:])]
    commits = git(root, 'rev-list', '--reverse', '--topo-order', after,
                  *['^' + sha for sha in excluded]).splitlines()
    # A new name for an existing commit still validates once; the job deduplicates.
    return commits or [after]


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--kind', choices=['runner', 'cli'], required=True)
    p.add_argument('--commit', required=True)
    p.add_argument('--output', type=Path)
    p.add_argument('--lines', action='store_true')
    a = p.parse_args()
    selected = classify(Path.cwd(), a.commit, a.kind)
    result = json.dumps(selected, indent=2) + '\n'
    if a.output:
        a.output.write_text(result)
    if a.lines:
        print(selected['version'] + '\n' + str(selected['release']).lower())
    elif not a.output:
        print(result, end='')
