from pathlib import Path
import tempfile
import unittest
from runtime_identity import prepare


class IdentityTests(unittest.TestCase):
    def test_shadow_only_registered_script_and_no_cache_recursion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); script = root / 'scripts/test/test.gml'
            script.parent.mkdir(parents=True); script.write_text('show_debug_message(GM_runtime_version);\n')
            yyp = root / 'game.yyp'; yyp.write_text('{"resources":[{"id":{"path":"scripts/test/test.yy"}},{"id":{"path":"scripts/stub/stub.yy"}}],}')
            (root / '.gm-test').mkdir(); (root / '.gm-test/large').write_text('cache')
            (root / 'scripts/aaa').mkdir(); (root / 'scripts/aaa/unused.gml').write_text('unused')
            result = prepare(yyp, root / '.gm-test/invocation/project', '2024.14.4.268-c2')
            dest = Path(result['project']).parent
            self.assertNotIn('#macro', script.read_text())
            self.assertIn('#macro GM_runtime_version "2024.14.4.268-c2"', (dest / 'scripts/test/test.gml').read_text())
            self.assertEqual((dest / 'scripts/aaa/unused.gml').read_text(), 'unused')
            self.assertFalse((dest / '.gm-test').exists())

    def test_existing_macro_and_reused_output_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); script = root / 'scripts/test/test.gml'
            script.parent.mkdir(parents=True); script.write_text('#macro GM_runtime_version "wrong"\n')
            yyp = root / 'game.yyp'; yyp.write_text('{"path":"scripts/test/test.yy"}')
            with self.assertRaises(ValueError): prepare(yyp, root / '.gm-out/project', '2024.14.4.268-c2')
            with self.assertRaises(ValueError): prepare(yyp, root / '.gm-out/project', '2024.14.4.268-c2')
