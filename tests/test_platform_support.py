"""Cross-platform Mesh XR installer and honest desktop-vs-OpenXR capability tests."""
import importlib.util
import pathlib
import tomllib
import unittest
from types import SimpleNamespace as NS

ROOT = pathlib.Path(__file__).resolve().parents[1]
module_path = ROOT / 'blender_xr' / 'platform_support.py'
spec = importlib.util.spec_from_file_location('mesh_xr_platform_support', module_path)
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)


class DesktopSupportTests(unittest.TestCase):
    def test_manifest_covers_existing_desktops_and_both_macs(self):
        manifest = tomllib.loads((ROOT / 'blender_xr' / 'blender_manifest.toml').read_text())
        self.assertEqual(set(manifest['platforms']), set(support.DESKTOP_EXTENSION_TARGETS))
        self.assertEqual(manifest['wheels'], ['./wheels/openvr-2.12.1401-py3-none-any.whl'])
        self.assertNotIn('ios', ' '.join(manifest['platforms']))
        self.assertNotIn('android', ' '.join(manifest['platforms']))

    def test_platform_mapping_for_apple_silicon_and_intel(self):
        cases = {
            ('Windows', 'AMD64'): 'windows-x64',
            ('Windows', 'ARM64'): None,
            ('Linux', 'x86_64'): 'linux-x64',
            ('Darwin', 'arm64'): 'macos-arm64',
            ('Darwin', 'x86_64'): 'macos-x64',
            ('iOS', 'arm64'): None,
            ('Linux', 'aarch64'): None,
            ('Android', 'arm64'): None,
        }
        for (system, cpu), expected in cases.items():
            with self.subTest(system=system, cpu=cpu):
                self.assertEqual(support.desktop_platform(system, cpu), expected)

    def test_vr_requires_compiled_openxr(self):
        for tag in (('Windows', 'AMD64'), ('Linux', 'x86_64'), ('Darwin', 'arm64')):
            response = support.support_info((5, 2, 2), False, *tag)
            self.assertTrue(response['desktop'])
            self.assertFalse(response['vr'])
            self.assertIn('OpenXR', response['message'])

    def test_macos_5_1_plus_experimental_openxr(self):
        old = support.support_info((4, 5, 0), True, 'Darwin', 'arm64')
        self.assertTrue(old['desktop'])
        self.assertFalse(old['vr'])
        new = support.support_info((5, 2, 2), True, 'Darwin', 'arm64')
        self.assertTrue(new['desktop'])
        self.assertTrue(new['vr'])
        self.assertIn('experimental', new['message'])

    def test_intel_macos_blender_version_limit(self):
        old = support.support_info((4, 5, 0), False, 'Darwin', 'x86_64')
        self.assertTrue(old['desktop'])
        current = support.support_info((5, 2, 2), True, 'Darwin', 'x86_64')
        self.assertFalse(current['desktop'])
        self.assertFalse(current['vr'])
        self.assertIn('Apple Silicon', current['message'])

    def test_unsupported_host_is_rejected(self):
        r = support.support_info((5, 2, 2), True, 'OtherOS', 'arm64')
        self.assertFalse(r['desktop'])
        self.assertFalse(r['vr'])
        self.assertIn('desktop Blender', r['message'])

    def test_runtime_requires_headset_not_just_package(self):
        info = support.support_info((5, 2, 2), True, 'Windows', 'AMD64')
        self.assertTrue(info['vr'])
        self.assertIn('active OpenXR runtime', info['message'])
        # No new Windows ARM64 support is added during the macOS-focused update.
        self.assertFalse(support.support_info((5, 2, 2), True,
                      'Windows', 'ARM64')['desktop'])

    def test_blender_info_wrapper(self):
        fake = NS(app=NS(version=(5, 2, 2),build_options=NS(xr_openxr=False)))
        info = support.current_info(fake)
        self.assertFalse(info['vr'])


if __name__ == '__main__':
    unittest.main()
