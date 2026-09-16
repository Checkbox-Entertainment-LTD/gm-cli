#!/usr/bin/env python3
"""Build metadata and immutable publication for an already tested CLI package."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import urllib.request
from cli_distribution import GitHub, REPOSITORY, digest, safe_extract, validate_manifest
from commit_policy import classify


def stamp(root):
    version = (root / 'ci/release-version.txt').read_text().strip()
    for filename in ['package.json', 'package-lock.json']:
        file = root / filename
        value = json.loads(file.read_text()); value['version'] = version
        if filename == 'package-lock.json': value['packages']['']['version'] = version
        file.write_text(json.dumps(value, indent=2) + '\n')


def metadata(root, package):
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    selected = classify(root, commit, 'cli')
    if not selected['release']: raise ValueError('CLI publication requires a qualifying version-bump commit')
    version = selected['version']
    node_version = (root / '.node-version').read_text().strip()
    url = 'https://nodejs.org/dist/v' + node_version + '/SHASUMS256.txt'
    with urllib.request.urlopen(url, timeout=60) as r:
        checksums = dict((name.lstrip('*'), sha) for sha, name in (line.split() for line in r.read().decode().splitlines()))
    node_assets = {}
    for host in ['linux-x64', 'darwin-arm64']:
        name = 'node-v' + node_version + '-' + host + '.tar.gz'
        node_assets[host] = {'name': name, 'sha256': checksums[name]}
    with tempfile.TemporaryDirectory() as tmp:
        safe_extract(package, Path(tmp), 'package')
        files = {str(p.relative_to(tmp)): digest(p) for p in sorted(Path(tmp).rglob('*')) if p.is_file()}
        if json.loads((Path(tmp) / 'package/package.json').read_text())['version'] != version:
            raise ValueError('Packaged CLI version differs from release version')
    return validate_manifest({'schema': 1, 'product': 'checkbox-gm-cli', 'version': version, 'commit': commit,
                              'node': {'version': node_version, 'artifacts': node_assets}, 'files': files,
                              'package': {'name': package.name, 'sha256': digest(package), 'size': package.stat().st_size}})


def publish(manifest, package):
    gh = GitHub(); tag = 'cli/' + manifest['version']
    if gh.api('immutable-releases')['enabled'] is not True: raise ValueError('Enable immutable CLI releases')
    reservation = gh.api('git/ref/tags/' + tag)
    if reservation and (reservation['object']['type'] != 'commit' or reservation['object']['sha'] != manifest['commit']):
        raise ValueError('CLI version already belongs to another source commit')
    if not reservation:
        gh.api('git/refs', 'POST', {'ref': 'refs/tags/' + tag, 'sha': manifest['commit']})
    release = gh.api('releases/tags/' + tag)
    if release and release.get('immutable'):
        from cli_distribution import resolve
        if resolve(gh, manifest['version'])['manifest'] != manifest: raise ValueError('Published CLI bytes differ')
        print(release['html_url']); return
    if release and (not release.get('draft') or release.get('body') != 'Tested CLI package; source ' + manifest['commit']):
        raise ValueError('Unexpected existing CLI release')
    if not release: release = gh.api('releases', 'POST', {'tag_name': tag, 'target_commitish': manifest['commit'],
                    'name': 'Checkbox GM CLI ' + manifest['version'], 'draft': True,
                    'prerelease': False, 'make_latest': 'false',
                    'body': 'Tested CLI package; source ' + manifest['commit']})
    file = package.parent / 'cli-release.json'
    file.write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    env = dict(os.environ, GH_TOKEN=gh.token)
    for path in [file, package]:
        current = gh.api('releases/' + str(release['id']))
        found = [a for a in current['assets'] if a['name'] == path.name]
        if found:
            if len(found) != 1 or found[0]['size'] != path.stat().st_size or found[0].get('digest') != 'sha256:' + digest(path):
                raise ValueError('Existing draft asset differs; refusing overwrite')
        else:
            subprocess.run([os.environ.get('GH_BIN', 'gh'), 'release', 'upload', tag, str(path),
                            '--repo', REPOSITORY], env=env, check=True)
    current = gh.api('releases/' + str(release['id']))
    expected = {p.name: ('sha256:' + digest(p), p.stat().st_size) for p in [file, package]}
    actual = {a['name']: (a.get('digest'), a['size']) for a in current['assets']}
    if actual != expected or len(actual) != len(current['assets']): raise ValueError('CLI draft inventory mismatch')
    sealed = gh.api('releases/' + str(release['id']), 'PATCH', {'draft': False, 'make_latest': 'false'})
    if sealed.get('immutable') is not True: raise ValueError('CLI publication is not immutable')
    print(sealed['html_url'])


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['stamp', 'publish'])
    p.add_argument('--package', type=Path)
    a = p.parse_args()
    if a.action == 'stamp': stamp(Path.cwd())
    else:
        root = Path.cwd()
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        candidate = Path.home() / '.local/share/checkbox-ci/cli-candidates' / commit
        if not candidate.exists():
            import shutil
            candidate.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=candidate.parent, prefix='candidate-') as tmp:
                scratch = Path(tmp)
                m = metadata(root, a.package)
                shutil.copy2(a.package, scratch / a.package.name)
                (scratch / 'cli-release.json').write_text(json.dumps(m, sort_keys=True, indent=2) + '\n')
                os.rename(scratch, candidate)
        m = validate_manifest(json.loads((candidate / 'cli-release.json').read_text()))
        package = candidate / m['package']['name']
        if m['commit'] != commit or digest(package) != m['package']['sha256']: raise ValueError('Candidate identity differs')
        publish(m, package)
        import shutil
        # Jenkins archives the exact published candidate, also on a retry where
        # a fresh npm pack happened to produce different bytes.
        shutil.copy2(package, a.package)
        shutil.copy2(candidate / 'cli-release.json', a.package.parent / 'cli-release.json')
