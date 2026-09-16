#!/usr/bin/env python3
"""Private CLI release resolution and verified, atomic worker installation.

Standard-library bootstrap: deliberately independent of the CLI it installs.
"""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = 'Checkbox-Entertainment-LTD/gm-cli'
VERSION = re.compile(r'(\d+)\.(\d+)\.(\d+)-checkbox\.([1-9]\d*)\Z')
ROOT = Path.home() / '.local/lib/checkbox-gm-cli'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()


def version_key(value):
    m = VERSION.fullmatch(value)
    if not m or any(str(int(x)) != x for x in m.groups()):
        raise ValueError('Invalid CLI release version')
    return tuple(map(int, m.groups()))


class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        p = urllib.parse.urlparse(newurl)
        if p.scheme != 'https' or p.hostname not in {'api.github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'}:
            raise ValueError('Unexpected release redirect')
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if p.hostname != urllib.parse.urlparse(req.full_url).hostname: new.remove_header('Authorization')
        return new


class GitHub:
    def __init__(self):
        self.token = os.environ.get('GH_TOKEN') or os.environ.get('GIT_PASSWORD')
        if not self.token:
            if os.environ.get('JENKINS_URL'): raise ValueError('Bind GitHub App credentials for CLI download')
            self.token = subprocess.check_output(['gh', 'auth', 'token'], text=True, stderr=subprocess.DEVNULL).strip()
        self.opener = urllib.request.build_opener(Redirect())

    def api(self, path, method='GET', body=None, binary=False):
        headers = {'Authorization': 'Bearer ' + self.token, 'Cache-Control': 'no-cache',
                   'Accept': 'application/octet-stream' if binary else 'application/vnd.github+json',
                   'X-GitHub-Api-Version': '2022-11-28'}
        data = None if body is None else json.dumps(body).encode()
        if data is not None: headers['Content-Type'] = 'application/json'
        req = urllib.request.Request('https://api.github.com/repos/' + REPOSITORY + '/' + path,
                                     headers=headers, data=data, method=method)
        try:
            with self.opener.open(req, timeout=120) as response:
                return response.read() if binary else json.load(response)
        except urllib.error.HTTPError as e:
            if e.code == 404 and method == 'GET':
                return None
            raise RuntimeError('CLI GitHub request failed: HTTP ' + str(e.code)) from None

    def download(self, asset, dest):
        data = self.api('releases/assets/' + str(asset['id']), binary=True)
        if len(data) != asset['size'] or hashlib.sha256(data).hexdigest() != asset['sha256']:
            raise ValueError('CLI release asset size/hash differs')
        Path(dest).write_bytes(data)


def asset_identity(asset):
    h = asset.get('digest', '')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', h) or type(asset.get('id')) is not int or asset.get('size', 0) <= 0:
        raise ValueError('Missing release asset identity')
    return {'id': asset['id'], 'name': asset['name'], 'size': asset['size'], 'sha256': h[7:]}


def validate_manifest(m):
    if m.get('schema') != 1 or m.get('product') != 'checkbox-gm-cli': raise ValueError('Invalid CLI manifest')
    version_key(m['version'])
    if not re.fullmatch(r'[0-9a-f]{40}', m['commit']): raise ValueError('Invalid CLI commit')
    if not re.fullmatch(r'\d+\.\d+\.\d+', m['node']['version']): raise ValueError('Invalid Node version')
    for host in ('linux-x64', 'darwin-arm64'):
        a = m['node']['artifacts'][host]
        expected = 'node-v' + m['node']['version'] + '-' + host + '.tar.gz'
        if a['name'] != expected or not re.fullmatch(r'[0-9a-f]{64}', a['sha256']):
            raise ValueError('Invalid Node artifact')
    if not re.fullmatch(r'[0-9a-f]{64}', m['package']['sha256']): raise ValueError('Invalid CLI hash')
    if not m['files'] or 'package/dist/cli.js' not in m['files']: raise ValueError('Missing runnable CLI')
    return m


def resolve(github=None, exact=None):
    gh = github or GitHub()
    releases = []
    for page in range(1, 1001):
        batch = gh.api('releases?per_page=100&page=' + str(page))
        releases.extend(r for r in batch if not r['draft'] and not r['prerelease']
                        and r.get('immutable') is True and r['tag_name'].startswith('cli/')
                        and VERSION.fullmatch(r['tag_name'][4:]))
        if len(batch) < 100: break
    else: raise ValueError('Too many releases to resolve completely')
    if exact: releases = [r for r in releases if r['tag_name'] == 'cli/' + exact]
    if not releases: raise ValueError('No complete immutable CLI release is available')
    release = max(releases, key=lambda r: version_key(r['tag_name'][4:]))
    assets = {a['name']: a for a in release['assets']}
    if len(assets) != len(release['assets']) or 'cli-release.json' not in assets: raise ValueError('Ambiguous CLI inventory')
    ma = asset_identity(assets['cli-release.json'])
    with tempfile.TemporaryDirectory() as tmp:
        file = Path(tmp) / 'manifest.json'; gh.download(ma, file)
        manifest = validate_manifest(json.loads(file.read_bytes()))
    if release['tag_name'] != 'cli/' + manifest['version']: raise ValueError('CLI tag/version mismatch')
    tag = gh.api('git/ref/tags/' + urllib.parse.quote(release['tag_name'], safe=''))
    if not tag or tag['object'].get('sha') != manifest['commit'] or tag['object'].get('type') != 'commit':
        raise ValueError('CLI release source mismatch')
    package = manifest['package']
    if set(assets) != {'cli-release.json', package['name']}: raise ValueError('Unexpected CLI assets')
    pa = asset_identity(assets[package['name']])
    if any(pa[k] != package[k] for k in ('name', 'sha256', 'size')): raise ValueError('CLI asset differs from manifest')
    return {'schema': 1, 'repository': REPOSITORY, 'release_id': release['id'],
            'manifest_sha256': ma['sha256'], 'manifest': manifest, 'package': pa}


def safe_extract(archive, destination, prefix, links=False):
    with tarfile.open(archive) as tar:
        seen = set()
        members = tar.getmembers()
        for m in members:
            p = PurePosixPath(m.name)
            if (p.is_absolute() or '..' in p.parts or '\\' in m.name or not p.parts
                    or p.parts[0] != prefix or p.as_posix() != m.name.rstrip('/')
                    or p.as_posix() in seen): raise ValueError('Unsafe archive path')
            seen.add(p.as_posix())
            if not (m.isfile() or m.isdir() or (links and m.issym())): raise ValueError('Unsafe archive entry')
            if m.issym():
                target = (destination / m.name).parent / m.linkname
                if not target.resolve().is_relative_to((destination / prefix).resolve()): raise ValueError('Unsafe archive link')
        # Files cannot be written through a link, regardless of archive ordering.
        symlinks = {m.name.rstrip('/') for m in members if m.issym()}
        if any(str(p) in symlinks for m in members for p in PurePosixPath(m.name).parents):
            raise ValueError('Archive traverses a symlink')
        for m in members:
            m.uid = m.gid = 0; m.uname = m.gname = ''; m.mode &= 0o777
        tar.extractall(destination, members=members, filter='fully_trusted') if hasattr(tarfile, 'data_filter') else tar.extractall(destination, members=members)


def verify_files(directory, files):
    for name, expected in files.items():
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name or p.parts[0] != 'package': raise ValueError('Invalid inventory path')
        file = directory / name
        if file.is_symlink() or digest(file) != expected: raise ValueError('Installed CLI file differs: ' + name)
    actual = {str(p.relative_to(directory)) for p in (directory / 'package').rglob('*') if p.is_file()}
    if actual != set(files): raise ValueError('Installed CLI inventory differs')


@contextlib.contextmanager
def locked(root, key):
    root.mkdir(parents=True, exist_ok=True)
    with (root / (key + '.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def install(selection, github=None, root=ROOT):
    if selection.get('repository') != REPOSITORY: raise ValueError('Unexpected CLI repository')
    m = validate_manifest(selection['manifest'])
    asset = selection['package']
    if any(asset[k] != m['package'][k] for k in ('name', 'size', 'sha256')): raise ValueError('Selection package mismatch')
    key = asset['sha256']; destination = root / key
    with locked(root, key):
        if not destination.exists():
            with tempfile.TemporaryDirectory(dir=root, prefix='install-') as tmp:
                scratch = Path(tmp)
                (github or GitHub()).download(asset, scratch / 'artifact.tgz')
                if digest(scratch / 'artifact.tgz') != key: raise ValueError('Downloaded CLI archive differs')
                safe_extract(scratch / 'artifact.tgz', scratch, 'package')
                verify_files(scratch, m['files'])
                os.rename(scratch, destination)
        if digest(destination / 'artifact.tgz') != key: raise ValueError('Cached CLI archive differs')
        verify_files(destination, m['files'])
    node = install_node(m['node'], root / 'node')
    return node, destination / 'package/dist/cli.js'


def install_node(spec, root):
    host = {'Linux': 'linux', 'Darwin': 'darwin'}.get(platform.system())
    arch = {'x86_64': 'x64', 'arm64': 'arm64', 'aarch64': 'arm64'}.get(platform.machine())
    a = spec['artifacts'].get(str(host) + '-' + str(arch))
    if not a: raise ValueError('Unsupported CLI worker host')
    key = a['sha256']; destination = root / key
    name = a['name'][:-7]
    with locked(root, key):
        if not destination.exists():
            with tempfile.TemporaryDirectory(dir=root, prefix='node-') as tmp:
                scratch = Path(tmp); archive = scratch / 'node.tar.gz'
                url = 'https://nodejs.org/dist/v' + spec['version'] + '/' + a['name']
                with urllib.request.urlopen(url, timeout=120) as response, archive.open('wb') as f:
                    shutil.copyfileobj(response, f)
                if digest(archive) != key: raise ValueError('Node archive hash differs')
                safe_extract(archive, scratch, name, links=True)
                # Verify the executable against this verified archive on every use.
                hashes = {str(p.relative_to(scratch)): digest(p) for p in (scratch / name / 'bin').iterdir() if p.is_file() and not p.is_symlink()}
                (scratch / 'executables.json').write_text(json.dumps(hashes))
                os.rename(scratch, destination)
        if digest(destination / 'node.tar.gz') != key: raise ValueError('Cached Node archive differs')
        # Verify all Node/npm files against the checksum-verified archive. A
        # mutable sidecar is not an independent source of expected file hashes.
        with tarfile.open(destination / 'node.tar.gz') as tar:
            for member in tar.getmembers():
                file = destination / member.name
                if member.isfile():
                    expected = hashlib.sha256(tar.extractfile(member).read()).hexdigest()
                    if file.is_symlink() or digest(file) != expected: raise ValueError('Cached Node file differs')
                elif member.issym():
                    if not file.is_symlink() or os.readlink(file) != member.linkname: raise ValueError('Cached Node link differs')
        node = destination / name / 'bin/node'
        if subprocess.check_output([str(node), '--version'], text=True).strip() != 'v' + spec['version']:
            raise ValueError('Node version mismatch')
        return node
