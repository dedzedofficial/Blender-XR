"""Development packages must not be published as stable by the release workflow."""
from pathlib import Path
from tempfile import TemporaryDirectory
import runpy
import tomllib
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_release_ready import check_release_ready

version = runpy.run_path(str(ROOT / 'blender_xr/version.py'))
manifest = tomllib.loads((ROOT / 'blender_xr/blender_manifest.toml').read_text())
assert manifest['version'] == version['VERSION_TEXT']
assert (ROOT / 'blender_xr/README.md').read_text().startswith('# Mesh XR v' + version['VERSION_TEXT'] + '\n')
assert (ROOT / 'RELEASE_NOTES.md').read_text().startswith('# Mesh XR v' + version['VERSION_TEXT'])
with TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'blender_xr').mkdir()
    source = root / 'blender_xr/version.py'
    for channel in ('development', 'candidate', None):
        source.write_text('RELEASE_CHANNEL = ' + repr(channel))
        try:
            check_release_ready(root)
        except ValueError:
            pass
        else:
            raise AssertionError('Non-stable package accepted for publication')
    source.write_text('RELEASE_CHANNEL = "stable"')
    check_release_ready(root)
print('PASS version consistency and stable-publication guard')
