import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from cli_distribution import digest, install, resolve, safe_extract


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.package = self.root / 'cli.tgz'
        content = b'console.log("tested CLI");'
        with tarfile.open(self.package, 'w:gz') as tar:
            m = tarfile.TarInfo('package/dist/cli.js'); m.size = len(content)
            tar.addfile(m, io.BytesIO(content))
        self.manifest = {'schema': 1, 'product': 'checkbox-gm-cli', 'version': '2.3.0-checkbox.2',
                         'commit': 'a' * 40, 'node': {'version': '24.18.0', 'artifacts': {
                             h: {'name': 'node-v24.18.0-' + h + '.tar.gz', 'sha256': 'b' * 64}
                             for h in ['linux-x64', 'darwin-arm64']}},
                         'package': {'name': 'cli.tgz', 'size': self.package.stat().st_size, 'sha256': digest(self.package)},
                         'files': {'package/dist/cli.js': hashlib.sha256(content).hexdigest()}}
        self.selection = {'repository': 'Checkbox-Entertainment-LTD/gm-cli', 'manifest': self.manifest,
                          'package': dict(self.manifest['package'], id=1)}

    def test_cached_install_needs_no_download_and_rejects_modified_files(self):
        data = self.package.read_bytes()
        class FakeGitHub:
            calls = 0
            def download(self, asset, dest): self.calls += 1; dest.write_bytes(data)
        gh = FakeGitHub()
        with patch('cli_distribution.install_node', return_value=Path('/node')):
            _, cli = install(self.selection, gh, self.root / 'cache')
            install(self.selection, gh, self.root / 'cache')
            self.assertEqual(gh.calls, 1)
            cli.write_text('tampered')
            with self.assertRaises(ValueError): install(self.selection, gh, self.root / 'cache')

    def test_traversal_symlinks_and_duplicate_members_rejected(self):
        for names in [['package/../../escape'], ['package/a', 'package/a']]:
            with tarfile.open(self.package, 'w:gz') as tar:
                for name in names:
                    m = tarfile.TarInfo(name); m.size = 1; tar.addfile(m, io.BytesIO(b'x'))
            with self.assertRaises(ValueError): safe_extract(self.package, self.root / 'out', 'package')
        with tarfile.open(self.package, 'w:gz') as tar:
            m = tarfile.TarInfo('package/link'); m.type = tarfile.SYMTYPE; m.linkname = '/tmp'; tar.addfile(m)
        with self.assertRaises(ValueError): safe_extract(self.package, self.root / 'out', 'package', links=True)

    def test_selects_highest_complete_immutable_version_not_publication_order(self):
        manifest = self.manifest
        encoded = json.dumps(manifest).encode()
        class FakeGitHub:
            def api(self, path):
                if path.startswith('releases?'):
                    def release(v, **extra):
                        return dict(id=1, tag_name='cli/' + v, draft=False, prerelease=False, immutable=True,
                                    assets=[{'id': 2, 'name': 'cli-release.json', 'size': len(encoded),
                                             'digest': 'sha256:' + hashlib.sha256(encoded).hexdigest()},
                                            {'id': 3, **manifest['package'], 'digest': 'sha256:' + manifest['package']['sha256']}], **extra)
                    newer = release('2.3.0-checkbox.2')
                    old = release('2.3.0-checkbox.1')
                    draft = release('2.3.0-checkbox.9'); draft['draft'] = True
                    return [old, draft, newer]
                return {'object': {'sha': 'a' * 40, 'type': 'commit', 'url': 'api'}}
            def download(self, asset, path): path.write_bytes(encoded)
        self.assertEqual(resolve(FakeGitHub())['manifest']['version'], '2.3.0-checkbox.2')

    def test_corrupt_archive_never_becomes_installed(self):
        class FakeGitHub:
            def download(self, asset, dest): dest.write_bytes(b'bad archive')
        with self.assertRaises(ValueError): install(self.selection, FakeGitHub(), self.root / 'cache')
        self.assertFalse((self.root / 'cache' / self.selection['package']['sha256']).exists())
