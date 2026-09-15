#!/usr/bin/env python3
"""Release contracts and verification, independent of Jenkins and storage."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

PRODUCT = 'checkbox-runner'
PLATFORMS = {'ios', 'android'}
CHANNELS = {'internal', 'stable'}


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9][0-9a-z]*(?:[.-][0-9a-z]+)*', value) or len(value) > 64:
        raise ValueError('Version must start with a digit and use lowercase letters, digits, dots or hyphens (max 64 characters)')
    return value


def hex_value(value, length):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{%d}' % length, value):
        raise ValueError('Invalid %d-character digest' % length)
    return value


def inventory(archive):
    members = archive.getmembers()
    seen = set()
    for member in members:
        p = PurePosixPath(member.name)
        if (not p.parts or p.parts[0] != 'runner' or p.is_absolute()
                or '..' in p.parts or '\\' in member.name
                or p.as_posix() != member.name.rstrip('/')
                or p.as_posix() in seen or not (member.isfile() or member.isdir())):
            raise ValueError('Unsafe or duplicate archive member: ' + member.name)
        seen.add(p.as_posix())
    return members


def read_package(path, expected_sha=None):
    """Verify every packaged byte before extracting or trusting its manifest."""
    if expected_sha is not None and digest(path) != hex_value(expected_sha, 64):
        raise ValueError('Artifact SHA-256 does not match the pinned checksum')
    with tarfile.open(path) as archive:
        members = inventory(archive)
        manifest_file = archive.extractfile('runner/manifest.json')
        if manifest_file is None:
            raise ValueError('Missing package manifest')
        manifest = json.load(manifest_file)
        if manifest.get('schema') not in (2, 3) or manifest.get('status') != 'complete':
            raise ValueError('Package is not a complete versioned release candidate')
        version(manifest.get('version'))
        hex_value(manifest.get('runner_commit'), 40)
        files = {m.name[len('runner/'):] for m in members if m.isfile() and m.name != 'runner/manifest.json'}
        if files != set(manifest.get('files', {})):
            raise ValueError('Manifest file inventory differs from the package')
        for name in sorted(files):
            h = hashlib.sha256()
            with archive.extractfile('runner/' + name) as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b''):
                    h.update(chunk)
            if h.hexdigest() != hex_value(manifest['files'][name], 64):
                raise ValueError('File checksum mismatch: ' + name)
    return manifest


def make_release(paths, release_version):
    version(release_version)
    artifacts = {}
    common = None
    for path in paths:
        path = Path(path)
        m = read_package(path)
        platform = m['platform']
        if platform not in PLATFORMS or platform in artifacts:
            raise ValueError('Unsupported or duplicate release platform')
        if m['version'] != release_version:
            raise ValueError('Candidate version differs from requested release')
        identity = {key: m[key] for key in ('runner_commit', 'lock', 'recipe_sha256')}
        if common is not None and common != identity:
            raise ValueError('Platforms were built from different source, dependencies or recipes')
        common = identity
        checks = m.get('validation', {})
        if m['schema'] == 3:
            validate_native_package(path, m)
        else:
            if checks.get('compile') is not True or checks.get('game_link') is not True:
                raise ValueError(platform + ': compilation and game-link evidence required before publishing')
            if not checks.get('report_sha256') or checks['report_sha256'] not in m['files'].values():
                raise ValueError('Game-link evidence must be included in the verified package')
            if platform == 'ios':
                report_name = 'game-link-audit/game-link-report.json'
                if m['files'].get(report_name) != checks['report_sha256']:
                    raise ValueError('Expected the iOS game-link report')
                with tarfile.open(path) as archive:
                    report = json.load(archive.extractfile('runner/' + report_name))
                if (report.get('error') or report.get('stock_link_succeeded') is not True
                        or report.get('rebuilt_link_succeeded') is not True
                        or report.get('mode') != 'candidate'
                        or report.get('rebuilt_library_sha256') != m['files'].get('libyoyo_yyc.a')):
                    raise ValueError('Game-link report does not validate this candidate library')
                for filename, slice_name in [('libyoyo_yyc.a', 'ios-arm64'),
                                             ('libyoyo_yyc_sim.a', 'ios-arm64_x86_64-simulator')]:
                    packaged = 'payload/yoyo_ios_runner_yyc.xcframework/' + slice_name + '/' + filename
                    if not m['files'].get(filename) or m['files'].get(packaged) != m['files'][filename]:
                        raise ValueError('XCFramework differs from the validated native libraries')
            else:
                raise ValueError('Android release validation adapter is not implemented yet')
        expected_name = 'runner-' + release_version + '-' + platform + '.tar.gz'
        if path.name != expected_name:
            raise ValueError('Unexpected artifact filename: ' + path.name)
        artifacts[platform] = {'name': path.name, 'sha256': digest(path), 'size': path.stat().st_size,
                               'validation': checks, 'toolchain': m['toolchain'],
                               'jenkins_build_url': m.get('jenkins_build_url')}
    if re.fullmatch(r'\d+\.\d+\.\d+\.\d+-c[1-9][0-9]*', release_version):
        if set(artifacts) != PLATFORMS or not all(a['validation'].get('native') is True for a in artifacts.values()):
            raise ValueError('Custom mobile releases require both natively validated platform packages')
        if common['lock']['runtime'] != release_version.split('-c')[0]:
            raise ValueError('Custom release version differs from its official runtime base')
    if not artifacts:
        raise ValueError('At least one platform is required')
    return {'schema': 1, 'product': PRODUCT, 'version': release_version,
            **common, 'artifacts': artifacts}


def validate_native_package(path, manifest):
    checks = manifest.get('validation', {})
    if checks.get('compile') is not True or checks.get('native') is not True:
        raise ValueError('Native compilation and validation required')
    if manifest['files'].get('native-validation.json') != checks.get('native_report_sha256'):
        raise ValueError('Native validation report is missing or differs')
    with tarfile.open(path) as archive:
        report = json.load(archive.extractfile('runner/native-validation.json'))
    if (report.get('status') != 'passed' or report.get('scope') != 'native-only'
            or report.get('platform') != manifest['platform'] or report.get('runtime') != manifest['lock']['runtime']):
        raise ValueError('Native validation identity differs')
    if manifest['platform'] == 'android':
        expected = {'payload/yyc/android/' + a + '/lib/libyoyo.a': [a] for a in ['arm64-v8a', 'x86_64']}
    else:
        root = 'payload/yoyo_ios_runner_yyc.xcframework/'
        expected = {root + 'ios-arm64/libyoyo_yyc.a': ['arm64'],
                    root + 'ios-arm64_x86_64-simulator/libyoyo_yyc_sim.a': ['arm64', 'x86_64']}
    if set(report.get('libraries', {})) != set(expected):
        raise ValueError('Native report does not cover exactly the required libraries')
    payload_libraries = {name for name in manifest['files'] if name.startswith('payload/') and name.endswith('.a')}
    if payload_libraries != set(expected):
        raise ValueError('Package includes missing or extra native libraries')
    for name, architectures in expected.items():
        entry = report['libraries'][name]
        if (entry.get('sha256') != manifest['files'].get(name)
                or entry.get('architectures') != architectures or not entry.get('relocatable_link_sha256')):
            raise ValueError('Native report does not validate the packaged library')


def validate_release(m):
    if m.get('schema') != 1 or m.get('product') != PRODUCT:
        raise ValueError('Unsupported release manifest')
    version(m.get('version'))
    hex_value(m.get('runner_commit'), 40)
    hex_value(m.get('recipe_sha256'), 64)
    if not re.fullmatch(r'\d+\.\d+\.\d+\.\d+', m.get('lock', {}).get('runtime', '')):
        raise ValueError('Exact GameMaker compatibility version required')
    if not m.get('artifacts') or not set(m['artifacts']) <= PLATFORMS:
        raise ValueError('Unsupported platform set')
    for platform, a in m['artifacts'].items():
        if a.get('name') != 'runner-' + m['version'] + '-' + platform + '.tar.gz':
            raise ValueError('Unexpected asset name')
        hex_value(a.get('sha256'), 64)
        if type(a.get('size')) is not int or a['size'] <= 0:
            raise ValueError('Invalid asset size')
        if a.get('validation', {}).get('compile') is not True or not (a['validation'].get('game_link') is True or a['validation'].get('native') is True):
            raise ValueError('Release lacks required automated validation')
    return m


def empty_registry():
    return {'schema': 1, 'revision': 0, 'channels': {}, 'revoked': {}, 'events': []}


def update_channel(registry, manifest, manifest_sha, channel, expected_revision,
                   actor, reason, timestamp, device_evidence=None):
    """Pure transition. Storage must CAS the entire registry when committing it."""
    validate_release(manifest)
    hex_value(manifest_sha, 64)
    if channel not in CHANNELS:
        raise ValueError('Channel must be internal or stable')
    if registry.get('schema') != 1 or registry.get('revision') != expected_revision:
        raise ValueError('Registry changed; inspect current channels and retry explicitly')
    if not actor.strip() or not reason.strip():
        raise ValueError('Actor and reason are required')
    if manifest['version'] in registry['revoked']:
        raise ValueError('Release is revoked')
    if channel == 'stable':
        if not isinstance(device_evidence, dict):
            raise ValueError('Stable requires device acceptance evidence')
        if device_evidence.get('release_manifest_sha256') != manifest_sha:
            raise ValueError('Device evidence refers to another release')
        if set(device_evidence.get('platforms', {})) != set(manifest['artifacts']):
            raise ValueError('Device evidence must cover every released platform')
        for p, a in manifest['artifacts'].items():
            e = device_evidence['platforms'][p]
            if e.get('artifact_sha256') != a['sha256'] or e.get('accepted') is not True or not e.get('tested_by') or not e.get('report'):
                raise ValueError('Incomplete device acceptance for ' + p)
    result = json.loads(json.dumps(registry))
    key = manifest['lock']['runtime'] + '/' + channel
    target = {'version': manifest['version'], 'manifest_sha256': manifest_sha}
    event = {'action': 'promote', 'channel': key, 'previous': result['channels'].get(key),
             'target': target, 'actor': actor, 'reason': reason, 'at': timestamp,
             'device_evidence': device_evidence}
    result['channels'][key] = target
    result['revision'] += 1
    result['events'].append(event)
    return result


def resolve_lock(manifest, manifest_sha, registry, platforms, runtime, channel=None):
    validate_release(manifest)
    hex_value(manifest_sha, 64)
    if manifest['version'] in registry['revoked']:
        raise ValueError('Release is revoked: ' + manifest['version'])
    if manifest['lock']['runtime'] != runtime:
        raise ValueError('Release is incompatible with the requested GameMaker runtime')
    if not platforms or not set(platforms) <= set(manifest['artifacts']):
        raise ValueError('Release does not contain every requested platform')
    if channel:
        key = runtime + '/' + channel
        if registry['channels'].get(key) != {'version': manifest['version'], 'manifest_sha256': manifest_sha}:
            raise ValueError('Channel target does not match the fetched release')
    return {'schema': 1, 'product': PRODUCT, 'version': manifest['version'],
            'manifest_sha256': manifest_sha, 'registry_revision': registry['revision'],
            'channel': channel, 'runtime': runtime, 'runner_commit': manifest['runner_commit'],
            'artifacts': {p: manifest['artifacts'][p] for p in sorted(set(platforms))}}
