import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request
from mobile_runtime import object_architectures, runtime_version, SafeRedirect, resolve, verified_lock


def ar(body):
    return b'!<arch>\n' + b'unit.o/         ' + b'0           0     0     100644  ' + str(len(body)).encode().ljust(10) + b'`\n' + body + (b'\n' if len(body)%2 else b'')


def elf(machine):
    data=bytearray(64); data[:6]=b'\x7fELF\x02\x01'; struct.pack_into('<H',data,18,machine); return bytes(data)


class RuntimeTests(unittest.TestCase):
    def test_exact_stock_and_custom_versions(self):
        self.assertEqual(runtime_version('2024.14.4.268'), ('2024.14.4.268',False))
        self.assertEqual(runtime_version('2024.14.4.268-c1'), ('2024.14.4.268',True))
        for invalid in ['2024.14.4','2024.14.4.268-C1','2024.14.4.268-c0','2024.14.4.268-c01','latest','2024.14.4.268-c1\n']:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError): runtime_version(invalid)

    def test_inspect_actual_object_headers_not_just_archive_filenames(self):
        self.assertEqual(object_architectures(ar(elf(183))), {'arm64'})
        self.assertEqual(object_architectures(ar(elf(62))), {'x86_64'})
        self.assertEqual(object_architectures(ar(elf(183)) + ar(elf(62))[8:]), {'arm64','x86_64'})

    def test_reject_truncated_and_non_native_archives(self):
        for data in [b'!<thin>\n',ar(b'not an object'),ar(elf(62))[:-10],b'!<arch>\n']:
            with self.subTest(data=data[:10]), self.assertRaises(ValueError): object_architectures(data)

    def test_fat_archive_cannot_reference_bytes_outside_itself(self):
        data=struct.pack('>IIIIIII',0xcafebabe,1,0x100000c,0,999,100,0)
        with self.assertRaisesRegex(ValueError,'Invalid fat archive'): object_architectures(data)

    def test_cross_host_redirect_never_forwards_token(self):
        request=Request('https://api.github.com/asset',headers={'Authorization':'Bearer private'})
        redirected=SafeRedirect().redirect_request(request,None,302,'found',{},'https://release-assets.githubusercontent.com/asset')
        self.assertIsNone(redirected.get_header('Authorization'))
        with self.assertRaises(ValueError): SafeRedirect().redirect_request(request,None,302,'found',{},'https://untrusted.example/asset')

    def test_unpublished_release_fails_without_stock_fallback_or_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary)/'release'
            with patch('mobile_runtime.GitHub') as github:
                github.return_value.json.return_value={'draft':False,'immutable':False}
                with self.assertRaisesRegex(ValueError,'not published and immutable'):
                    resolve('2024.14.4.268-c1',['ios'],out)
            self.assertFalse(out.exists())
            self.assertEqual(list(Path(temporary).iterdir()),[])

    def test_lock_cannot_select_different_version_or_platform(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'lock.json'
            path.write_text(json.dumps({'schema':1,'version':'2024.14.4.268','base':'2024.14.4.268','platforms':['ios'],'artifacts':{}}))
            verified_lock(path,'2024.14.4.268','ios')
            with self.assertRaises(ValueError): verified_lock(path,'2024.14.4.268','android')
            with self.assertRaises(ValueError): verified_lock(path,'2024.14.4.268-c1','ios')

if __name__=='__main__': unittest.main()

class AssemblyTests(unittest.TestCase):
    def setUp(self):
        import hashlib, tarfile
        from release_contract import canonical, make_release
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.version = '2024.14.4.268-c1'
        self.base = self.root / 'runtime-2024.14.4.268'; self.base.mkdir()
        (self.base / 'receipt.json').write_text('{"base":{},"android":{}}')
        from mobile_runtime import ANDROID_LIBRARIES
        stock = {}
        for name in ANDROID_LIBRARIES:
            file = self.base / name; file.parent.mkdir(parents=True); file.write_bytes(b'official-' + name.encode())
            stock[name] = hashlib.sha256(file.read_bytes()).hexdigest()
        paths = []
        for platform in ['android','ios']:
            prefix = 'payload/yyc/android/'
            libraries = ({prefix + abi + '/lib/libyoyo.a': [abi] for abi in ['arm64-v8a','x86_64']}
                if platform == 'android' else {'payload/yoyo_ios_runner_yyc.xcframework/ios-arm64/libyoyo_yyc.a':['arm64'],
                  'payload/yoyo_ios_runner_yyc.xcframework/ios-arm64_x86_64-simulator/libyoyo_yyc_sim.a':['arm64','x86_64']})
            files = {name: ar(elf(183 if arches == ['arm64-v8a'] else 62)) for name,arches in libraries.items()}
            hashes = {name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
            report = {'schema':1,'status':'passed','scope':'native-only','runtime':'2024.14.4.268','platform':platform,
              'libraries':{name:{'sha256':hashes[name],'architectures':arches,'relocatable_link_sha256':'f'*64}
                           for name,arches in libraries.items()}}
            files['native-validation.json'] = canonical(report)
            manifest={'schema':3,'version':self.version,'status':'complete','platform':platform,'runner_commit':'a'*40,
              'lock':{'runtime':'2024.14.4.268','android':{'stock_libraries':stock}},'recipe_sha256':'b'*64,
              'toolchain':{},'files':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()},
              'validation':{'compile':True,'native':True,'native_report_sha256':hashlib.sha256(files['native-validation.json']).hexdigest()}}
            files['manifest.json']=canonical(manifest)
            path=self.root/('runner-'+self.version+'-'+platform+'.tar.gz');paths.append(path)
            with tarfile.open(path,'w:gz') as archive:
                for name,data in files.items():
                    entry=tarfile.TarInfo('runner/'+name);entry.size=len(data);archive.addfile(entry,io.BytesIO(data))
        release=make_release(paths,self.version)
        (self.root/'release.json').write_bytes(canonical(release))
        self.lock=self.root/'lock.json'
        self.lock.write_text(json.dumps({'schema':1,'version':self.version,'base':'2024.14.4.268','platforms':['android'],
          'runner_commit':release['runner_commit'],'manifest_sha256':hashlib.sha256((self.root/'release.json').read_bytes()).hexdigest(),
          'artifacts':{'android':release['artifacts']['android']}}))

    def test_verified_replacements_are_isolated_and_base_is_unchanged(self):
        from mobile_runtime import assemble, digest
        first=self.root/'first';second=self.root/'second'
        original={p:digest(p) for p in self.base.rglob('libyoyo.a')}
        a=assemble(self.lock,self.version,'android',self.base,first)
        b=assemble(self.lock,self.version,'android',self.base,second)
        self.assertEqual(a['libraries'],b['libraries'])
        self.assertEqual({p:digest(p) for p in original},original)
        (first/next(iter(a['libraries']))).write_bytes(b'changed only first invocation')
        for path,value in b['libraries'].items():self.assertEqual(digest(second/path),value)
        with self.assertRaisesRegex(ValueError,'already exists'):assemble(self.lock,self.version,'android',self.base,second)

    def test_wrong_base_hash_fails_before_copy(self):
        from mobile_runtime import assemble
        next(self.base.rglob('libyoyo.a')).write_bytes(b'contaminated stock')
        destination=self.root/'bad'
        with self.assertRaisesRegex(ValueError,'base file hash differs'):
            assemble(self.lock,self.version,'android',self.base,destination)
        self.assertFalse(destination.exists())

    def test_changed_artifact_fails_before_assembly(self):
        from mobile_runtime import assemble
        package=self.root/('runner-'+self.version+'-android.tar.gz');package.write_bytes(package.read_bytes()+b'tampered')
        destination=self.root/'bad'
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            assemble(self.lock,self.version,'android',self.base,destination)
        self.assertFalse(destination.exists())

    def test_retired_signing_wrapper_rejected(self):
        from mobile_runtime import assemble
        wrapper=self.base/'android/runner/gradle/gradlew.real';wrapper.parent.mkdir(parents=True);wrapper.touch()
        with self.assertRaisesRegex(ValueError,'retired signing wrapper'):
            assemble(self.lock,self.version,'android',self.base,self.root/'bad')
