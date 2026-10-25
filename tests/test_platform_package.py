"""CI platform-neutral Blender extension ZIP integrity and declared host targets."""
from pathlib import Path
import hashlib
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
source = tomllib.loads((ROOT / 'blender_xr' / 'blender_manifest.toml').read_text())
version = source['version']
installer = ROOT / 'dist' / ('mesh-xr-v' + version + '.zip')
assert installer.exists(), installer
with zipfile.ZipFile(installer) as archive:
    assert archive.testzip() is None
    names = set(archive.namelist())
    built = tomllib.loads(archive.read('blender_manifest.toml').decode())
    assert built['version'] == version
    assert set(built['platforms']) == {
        'windows-x64', 'windows-arm64', 'linux-x64', 'macos-x64', 'macos-arm64'}
    assert built['wheels'] == ['./wheels/openvr-2.12.1401-py3-none-any.whl']
    for module in ('__init__.py', 'platform_support.py', 'hands_v080.py',
                   'radial_logic_v080.py', 'steamvr_hand_bridge.py'):
        assert module in names, module
    assert not any(name.endswith(('.exe','.dll','.dylib','.so')) for name in names)

digest = hashlib.sha256(installer.read_bytes()).hexdigest()
checksum = Path(str(installer) + '.sha256').read_text().split()[0]
assert digest == checksum
print('PASS universal desktop Blender extension:', installer.name, digest)
print('TARGETS:', ', '.join(built['platforms']))
print('NOTE: iOS/Android standalone and macOS headset runtimes are not implied.')
