#!/usr/bin/env python3
"""Verify immutable custom mobile releases and assemble isolated official runtimes."""
import argparse
import json
import mmap
import os
from pathlib import Path
import plistlib
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request

from release_contract import digest, read_package, inventory, validate_native_package, validate_release

REPOSITORY = 'Checkbox-Entertainment-LTD/GMS2-Runner-Main'
VERSION = re.compile(r'([0-9]+(?:\.[0-9]+){3})(?:-c([1-9][0-9]*))?\Z')
IOS_FRAMEWORK = 'yyc/ios/TemplateProject/${YYXCodeProjName}/Supporting Files/yoyo_ios_runner_yyc.xcframework'
IOS_LIBRARIES = {'ios-arm64/libyoyo_yyc.a': ['arm64'],
                 'ios-arm64_x86_64-simulator/libyoyo_yyc_sim.a': ['arm64', 'x86_64']}
ANDROID_LIBRARIES = {'yyc/android/arm64-v8a/lib/libyoyo.a': ['arm64-v8a'],
                     'yyc/android/x86_64/lib/libyoyo.a': ['x86_64']}


def runtime_version(value):
    match = VERSION.fullmatch(value)
    if not match:
        raise ValueError('Expected an exact A.B.C.D or lowercase A.B.C.D-cN runtime version')
    return match[1], bool(match[2])


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlparse(newurl)
        if parsed.scheme != 'https' or parsed.hostname not in {'api.github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'}:
            raise ValueError('Unexpected GitHub asset redirect')
        result = super().redirect_request(req, fp, code, msg, headers, newurl)
        if parsed.hostname != urllib.parse.urlparse(req.full_url).hostname:
            result.remove_header('Authorization')
        return result


class GitHub:
    def __init__(self):
        self.token = os.environ.get('GH_TOKEN') or os.environ.get('GIT_PASSWORD')
        if not self.token:
            if os.environ.get('CI'):
                raise ValueError('Bind GH_TOKEN for private custom runtime resolution')
            self.token = subprocess.check_output(['gh', 'auth', 'token'], text=True, stderr=subprocess.DEVNULL).strip()
        self.opener = urllib.request.build_opener(SafeRedirect())

    def open(self, path, binary=False):
        req = urllib.request.Request('https://api.github.com/repos/' + REPOSITORY + '/' + path,
            headers={'Authorization': 'Bearer ' + self.token,
                     'Accept': 'application/octet-stream' if binary else 'application/vnd.github+json',
                     'X-GitHub-Api-Version': '2022-11-28', 'Cache-Control': 'no-cache'})
        return self.opener.open(req, timeout=60)

    def json(self, path):
        with self.open(path) as response:
            return json.load(response)

    def download(self, asset, destination):
        if type(asset.get('id')) is not int or type(asset.get('size')) is not int or asset['size'] <= 0:
            raise ValueError('Invalid GitHub asset identity')
        with self.open('releases/assets/' + str(asset['id']), True) as response, destination.open('xb') as output:
            shutil.copyfileobj(response, output)
        if destination.stat().st_size != asset['size'] or asset.get('digest') != 'sha256:' + digest(destination):
            raise ValueError('GitHub asset size or SHA-256 differs')


def object_architectures(data, start=0, end=None):
    """Inspect every Mach-O/ELF object in ar archives, including fat Apple archives."""
    end = len(data) if end is None else end
    if start < 0 or end > len(data) or end - start < 8:
        raise ValueError('Truncated native library')
    magic = data[start:start+8]
    if magic[:4] in (b'\xca\xfe\xba\xbe', b'\xca\xfe\xba\xbf'):
        wide = magic[:4] == b'\xca\xfe\xba\xbf'
        count = struct.unpack_from('>I', data, start+4)[0]
        if count not in (1, 2): raise ValueError('Unexpected fat archive coverage')
        result = set(); ranges = []
        for i in range(count):
            entry = start+8+i*(32 if wide else 20)
            if entry+(32 if wide else 20) > end: raise ValueError('Truncated fat archive')
            offset, size = struct.unpack_from('>QQ' if wide else '>II', data, entry+8)
            if offset < 8+count*(32 if wide else 20) or start+offset+size > end:
                raise ValueError('Invalid fat archive slice')
            machine = struct.unpack_from('>I', data, entry)[0]
            expected = {0x100000c: 'arm64', 0x1000007: 'x86_64'}.get(machine)
            if expected is None or expected in result or any(offset < b and offset+size > a for a,b in ranges):
                raise ValueError('Invalid fat archive architecture or overlapping slices')
            actual = object_architectures(data, start+offset, start+offset+size)
            if actual != {expected}: raise ValueError('Fat archive header differs from its native objects')
            result |= actual; ranges.append((offset,offset+size))
        return result
    if magic == b'!<arch>\n':
        position = start+8; result = set()
        while position < end:
            if position+60 > end or data[position+58:position+60] != b'`\n':
                raise ValueError('Invalid native archive header')
            name = data[position:position+16].decode('ascii').strip()
            size = int(data[position+48:position+58].decode('ascii').strip())
            body = position+60; stop = body+size
            if size < 0 or stop > end: raise ValueError('Invalid native archive size')
            if name.startswith('#1/'):
                length = int(name[3:])
                if length < 0 or length > size: raise ValueError('Invalid BSD archive filename')
                name = data[body:body+length].rstrip(b'\0').decode('utf8'); body += length
            if name not in ('/', '//', '/SYM64/') and not name.startswith('__.SYMDEF'):
                result |= object_architectures(data, body, stop)
            position = stop+(size % 2)
        if not result: raise ValueError('Native archive contains no objects')
        return result
    if magic[:4] == b'\x7fELF':
        if end-start < 64 or data[start+4] != 2 or data[start+5] != 1:
            raise ValueError('Expected a 64-bit little-endian ELF object')
        machine = struct.unpack_from('<H', data, start+18)[0]
        return { {183: 'arm64', 62: 'x86_64'}[machine] }
    if magic[:4] == b'\xcf\xfa\xed\xfe':
        if end-start < 32: raise ValueError('Truncated Mach-O header')
        machine = struct.unpack_from('<I', data, start+4)[0]
        return { {0x100000c: 'arm64', 0x1000007: 'x86_64'}[machine] }
    raise ValueError('Unsupported native library object format')


def verify_library(path, architectures):
    with path.open('rb') as file, mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as data:
        actual = object_architectures(data)
    expected = {'arm64' if a == 'arm64-v8a' else a for a in architectures}
    if actual != expected: raise ValueError('Native architecture coverage differs: ' + path.name)


def verify_payload(root, platform):
    if platform == 'android':
        for name, architectures in ANDROID_LIBRARIES.items():
            verify_library(root / 'payload' / name, architectures)
    else:
        framework = root / 'payload/yoyo_ios_runner_yyc.xcframework'
        info = plistlib.loads((framework / 'Info.plist').read_bytes())
        entries = info.get('AvailableLibraries', [])
        if len(entries) != 2: raise ValueError('Expected device and simulator XCFramework slices')
        for name, arches in IOS_LIBRARIES.items():
            identifier, filename = name.split('/')
            match = [entry for entry in entries if entry.get('LibraryIdentifier') == identifier]
            if (len(match) != 1 or match[0].get('LibraryPath') != filename
                    or sorted(match[0].get('SupportedArchitectures', [])) != sorted(arches)
                    or match[0].get('SupportedPlatform') != 'ios'
                    or match[0].get('SupportedPlatformVariant') != ('simulator' if '_sim.' in filename else None)):
                raise ValueError('XCFramework metadata differs from required architecture coverage')
            verify_library(framework / name, arches)


def unpack_package(path, destination, version, platform, release, artifact):
    manifest = read_package(path, artifact['sha256'])
    if (manifest.get('schema') != 3 or manifest.get('version') != version or manifest.get('platform') != platform
            or any(manifest.get(key) != release.get(key) for key in ('runner_commit', 'lock', 'recipe_sha256'))):
        raise ValueError('Custom package identity differs from immutable release')
    validate_native_package(path, manifest)
    destination.mkdir()
    with tarfile.open(path) as archive:
        inventory(archive)
        archive.extractall(destination)
    root = destination / 'runner'
    verify_payload(root, platform)
    return root, manifest


def resolve(version, platforms, destination):
    base, custom = runtime_version(version)
    if not platforms or set(platforms) - {'ios', 'android'}:
        raise ValueError('Select ios and/or android')
    if destination.exists(): raise ValueError('Release output already exists')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.runtime-resolve-', dir=destination.parent))
    try:
        lock = {'schema': 1, 'version': version, 'base': base, 'platforms': sorted(set(platforms)), 'artifacts': {}}
        if custom:
            github = GitHub()
            tag = 'runner/' + version
            remote = github.json('releases/tags/' + urllib.parse.quote(tag, safe=''))
            if remote.get('draft') is not False or remote.get('immutable') is not True:
                raise ValueError('Custom runtime release is not published and immutable')
            assets = remote['assets']; names = [a['name'] for a in assets]
            if len(names) != len(set(names)) or names.count('release.json') != 1:
                raise ValueError('Ambiguous release assets')
            github.download(next(a for a in assets if a['name'] == 'release.json'), temporary / 'release.json')
            release = validate_release(json.loads((temporary / 'release.json').read_bytes()))
            if (release['version'] != version or release['lock']['runtime'] != base
                    or set(release['artifacts']) != {'ios', 'android'}):
                raise ValueError('Release does not match requested mobile runtime and official base')
            ref = github.json('git/ref/tags/' + tag)
            if ref['object'].get('type') != 'commit' or ref['object'].get('sha') != release['runner_commit']:
                raise ValueError('Release tag does not match its source commit')
            if set(names) != {'release.json'} | {a['name'] for a in release['artifacts'].values()}:
                raise ValueError('Release asset inventory differs')
            lock.update(manifest_sha256=digest(temporary / 'release.json'), runner_commit=release['runner_commit'],
                        release_id=remote['id'], artifacts={p: release['artifacts'][p] for p in lock['platforms']})
            packages = temporary / 'packages'; packages.mkdir()
            for platform, artifact in lock['artifacts'].items():
                asset = next(a for a in assets if a['name'] == artifact['name'])
                if asset.get('digest') != 'sha256:' + artifact['sha256'] or asset['size'] != artifact['size']:
                    raise ValueError('Immutable release asset differs from manifest')
                path = temporary / artifact['name']; github.download(asset, path)
                unpack_package(path, packages / platform, version, platform, release, artifact)
        (temporary / 'lock.json').write_text(json.dumps(lock, indent=2) + '\n')
        temporary.rename(destination)
    finally:
        if temporary.exists(): shutil.rmtree(temporary)
    return lock


def verified_lock(path, version, platform):
    lock = json.loads(path.read_bytes()); base, custom = runtime_version(version)
    if lock.get('schema') != 1 or lock.get('version') != version or lock.get('base') != base or platform not in lock.get('platforms', []):
        raise ValueError('Runtime lock differs from the requested version/platform')
    if not custom: return lock, None
    release_path = path.parent / 'release.json'
    if digest(release_path) != lock.get('manifest_sha256'): raise ValueError('Release manifest checksum differs from lock')
    release = validate_release(json.loads(release_path.read_bytes()))
    if (release['version'] != version or release['lock']['runtime'] != base
            or release['runner_commit'] != lock.get('runner_commit')
            or lock['artifacts'].get(platform) != release['artifacts'].get(platform)):
        raise ValueError('Release lock identity differs')
    return lock, release


def assemble(lock_path, version, platform, base_runtime, destination):
    lock, release = verified_lock(lock_path, version, platform)
    if release is None: raise ValueError('Assembly requires a custom runtime')
    if base_runtime.name != 'runtime-' + lock['base']:
        raise ValueError('Official runtime directory version differs')
    receipt = json.loads((base_runtime / 'receipt.json').read_bytes())
    if platform not in receipt or 'base' not in receipt:
        raise ValueError('Official runtime is missing required modules')
    if (base_runtime / 'android/runner/gradle/gradlew.real').exists():
        raise ValueError('Official runtime contains the retired signing wrapper; install a fresh official runtime')
    if destination.exists(): raise ValueError('Assembled runtime output already exists')
    with tempfile.TemporaryDirectory(prefix='gm-verify-') as scratch:
        package, manifest = unpack_package(lock_path.parent / lock['artifacts'][platform]['name'],
            Path(scratch) / platform, version, platform, release, lock['artifacts'][platform])
        expected = manifest['lock'][platform]['stock_libraries']
        if platform == 'android':
            if set(expected) != set(ANDROID_LIBRARIES): raise ValueError('Unexpected replacement destination set')
            replacements = {name: package / 'payload' / name for name in ANDROID_LIBRARIES}
            base_hashes = expected
        else:
            if set(expected) != {'libyoyo_yyc.a', 'libyoyo_yyc_sim.a'}: raise ValueError('Unexpected iOS base library set')
            replacements = {IOS_FRAMEWORK + '/' + name: package / 'payload/yoyo_ios_runner_yyc.xcframework' / name for name in IOS_LIBRARIES}
            base_hashes = {name: expected[Path(name).name] for name in replacements}
        for name, expected_sha in base_hashes.items():
            if digest(base_runtime / name) != expected_sha: raise ValueError('Official base file hash differs: ' + name)
        shutil.copytree(base_runtime, destination)
        if platform == 'ios':
            shutil.rmtree(destination / IOS_FRAMEWORK)
            shutil.copytree(package / 'payload/yoyo_ios_runner_yyc.xcframework', destination / IOS_FRAMEWORK)
        else:
            for name, source in replacements.items(): shutil.copy2(source, destination / name)
            for name in ['yyc/android/armv7', 'yyc/android/armeabi-v7a']:
                if (destination / name).exists(): shutil.rmtree(destination / name)
        hashes = {name: digest(destination / name) for name in replacements}
        if any(hashes[name] != digest(source) for name, source in replacements.items()):
            raise ValueError('Installed replacement hashes differ')
    record = {'schema': 1, 'version': version, 'base': lock['base'], 'platform': platform,
              'manifest_sha256': lock['manifest_sha256'], 'runner_commit': lock['runner_commit'],
              'artifact_sha256': lock['artifacts'][platform]['sha256'], 'libraries': hashes,
              'runtimeDirectory': str(destination.resolve()), 'baseLibraries': base_hashes}
    (destination / 'assembly.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


def install_ios(record_path, project):
    record = json.loads(record_path.read_bytes())
    if record.get('platform') != 'ios': raise ValueError('Expected an iOS assembly record')
    frameworks = list(project.rglob('yoyo_ios_runner_yyc.xcframework'))
    if len(frameworks) != 1: raise ValueError('Expected one fresh generated runner XCFramework')
    target = frameworks[0]
    if target.is_symlink() or not target.resolve().is_relative_to(project.resolve()):
        raise ValueError('Generated runner must be inside this invocation project')
    source = Path(record['runtimeDirectory']) / IOS_FRAMEWORK
    for name in IOS_LIBRARIES:
        key = IOS_FRAMEWORK + '/' + name
        if digest(source / name) != record['libraries'][key]: raise ValueError('Assembled runner was modified')
        if digest(target / name) not in (record['libraries'][key], record['baseLibraries'][key]):
            raise ValueError('Generated project has an unexpected runner')
    shutil.rmtree(target)
    shutil.copytree(source, target)
    for name in IOS_LIBRARIES:
        if digest(target / name) != record['libraries'][IOS_FRAMEWORK + '/' + name]:
            raise ValueError('Generated runner installation differs')


def uuid_set(path):
    output = subprocess.check_output(['xcrun', 'dwarfdump', '--uuid', str(path)], text=True)
    values = set(re.findall(r'UUID: ([A-Fa-f0-9-]+) \(([^)]+)\)', output))
    if not values: raise ValueError('Missing Mach-O UUID information')
    return values


def verify_ios_distribution(result_path, derived, ipa, symbols, output):
    import zipfile
    result = json.loads(result_path.read_bytes())
    selected = [(name, value) for name, value in result['outputs']['runnerLibraries'].items()
                if Path(name).name in ('libyoyo_yyc.a', 'libyoyo_interpreted.a')]
    if result['target'] != 'ios' or len(selected) != 1: raise ValueError('Expected an iOS device build record')
    name, expected = selected[0]
    staged = list(derived.rglob(Path(name).name))
    if not staged or any(digest(path) != expected for path in staged):
        raise ValueError('Xcode staged a different or missing runner; upload blocked')
    with tempfile.TemporaryDirectory(prefix='gm-ios-symbols-') as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(ipa) as archive:
            infos = [name for name in archive.namelist() if re.fullmatch(r'Payload/[^/]+[.]app/Info[.]plist', name)]
            if len(infos) != 1: raise ValueError('Expected exactly one IPA application')
            info = plistlib.loads(archive.read(infos[0])); executable = info['CFBundleExecutable']
            if Path(executable).name != executable: raise ValueError('Invalid app executable name')
            binary_name = str(Path(infos[0]).parent / executable)
            (root / 'application').write_bytes(archive.read(binary_name))
        with zipfile.ZipFile(symbols) as archive:
            files = [name for name in archive.namelist() if name.endswith('/Contents/Resources/DWARF/' + executable)]
            if len(files) != 1: raise ValueError('Expected one matching app dSYM in archived symbols')
            (root / 'symbols').write_bytes(archive.read(files[0]))
        application_uuids = uuid_set(root / 'application')
        if application_uuids != uuid_set(root / 'symbols'):
            raise ValueError('IPA and archived dSYM UUIDs do not match; upload blocked')
    record = {'schema': 1, 'runtime': result['runtime'], 'gameCommit': result.get('gameCommit'),
              'assembly': result.get('assembly'), 'runner_sha256': expected,
              'ipa_sha256': digest(ipa), 'symbols_sha256': digest(symbols),
              'uuids': sorted(application_uuids), 'bundle_id': info['CFBundleIdentifier'],
              'version': info['CFBundleShortVersionString'], 'build_number': info['CFBundleVersion']}
    with output.open('x') as file: json.dump(record, file, indent=2)
    return record


def verify_android_distribution(result_path, aab, keystore, alias, output):
    import base64
    import zipfile
    result = json.loads(result_path.read_bytes())
    if result['target'] != 'android': raise ValueError('Expected an Android build record')
    architectures = set()
    with zipfile.ZipFile(aab) as archive:
        for entry in archive.infolist():
            match = re.fullmatch(r'[^/]+/lib/([^/]+)/[^/]+[.]so', entry.filename)
            if not match: continue
            architecture = match[1]; architectures.add(architecture)
            expected = {'arm64-v8a': {'arm64'}, 'x86_64': {'x86_64'}}.get(architecture)
            if expected is None or object_architectures(archive.read(entry)) != expected:
                raise ValueError('AAB contains an unexpected native architecture')
    if architectures != {'arm64-v8a', 'x86_64'}: raise ValueError('AAB architecture coverage is incomplete')
    verification = subprocess.check_output(['jarsigner', '-J-Duser.language=en', '-verify', str(aab)], text=True)
    if 'jar verified.' not in verification: raise ValueError('AAB signature verification failed')
    public = subprocess.check_output(['keytool', '-exportcert', '-keystore', str(keystore), '-alias', alias,
                                      '-storepass:env', 'ANDROID_KEYSTORE_PASSWORD'], stderr=subprocess.PIPE)
    certificates = subprocess.check_output(['keytool', '-printcert', '-jarfile', str(aab), '-rfc'], text=True)
    matches = re.findall(r'-----BEGIN CERTIFICATE-----\s*(.*?)\s*-----END CERTIFICATE-----', certificates, re.S)
    if len(matches) != 1 or base64.b64decode(matches[0]) != public:
        raise ValueError('AAB was not signed by the selected keystore certificate')
    import hashlib
    record = {'schema': 1, 'runtime': result['runtime'], 'gameCommit': result.get('gameCommit'),
              'assembly': result.get('assembly'), 'architectures': sorted(architectures),
              'aab_sha256': digest(aab), 'signer_sha256': hashlib.sha256(public).hexdigest()}
    with output.open('x') as file: json.dump(record, file, indent=2)
    return record



def main():
    parser = argparse.ArgumentParser(description=__doc__); commands = parser.add_subparsers(dest='action', required=True)
    resolve_cmd = commands.add_parser('resolve'); resolve_cmd.add_argument('--version', required=True); resolve_cmd.add_argument('--platforms', required=True); resolve_cmd.add_argument('--output', type=Path, required=True)
    assemble_cmd = commands.add_parser('assemble'); assemble_cmd.add_argument('--lock', type=Path, required=True); assemble_cmd.add_argument('--version', required=True); assemble_cmd.add_argument('--platform', choices=['ios','android'], required=True); assemble_cmd.add_argument('--base-runtime', type=Path, required=True); assemble_cmd.add_argument('--output', type=Path, required=True)
    verify_cmd = commands.add_parser('verify-lock'); verify_cmd.add_argument('--lock', type=Path, required=True); verify_cmd.add_argument('--version', required=True); verify_cmd.add_argument('--platform', choices=['ios','android'], required=True)
    ios_cmd = commands.add_parser('install-ios'); ios_cmd.add_argument('--record', type=Path, required=True); ios_cmd.add_argument('--project', type=Path, required=True)
    verify_ios = commands.add_parser('verify-ios'); verify_ios.add_argument('--result', type=Path, required=True); verify_ios.add_argument('--derived-data', type=Path, required=True); verify_ios.add_argument('--ipa', type=Path, required=True); verify_ios.add_argument('--symbols', type=Path, required=True); verify_ios.add_argument('--output', type=Path, required=True)
    verify_android = commands.add_parser('verify-android'); verify_android.add_argument('--result', type=Path, required=True); verify_android.add_argument('--aab', type=Path, required=True); verify_android.add_argument('--keystore', type=Path, required=True); verify_android.add_argument('--alias', required=True); verify_android.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'resolve': result = resolve(args.version, args.platforms.split(','), args.output)
    elif args.action == 'assemble': result = assemble(args.lock, args.version, args.platform, args.base_runtime, args.output)
    elif args.action == 'verify-lock': result = verified_lock(args.lock, args.version, args.platform)[0]
    elif args.action == 'verify-ios': result = verify_ios_distribution(args.result, args.derived_data, args.ipa, args.symbols, args.output)
    elif args.action == 'verify-android': result = verify_android_distribution(args.result, args.aab, args.keystore, args.alias, args.output)
    else: result = install_ios(args.record, args.project)
    print(json.dumps(result))


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print('Custom runtime verification failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
