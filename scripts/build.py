"""Build a root-layout Blender extension ZIP and checksum from source."""
from pathlib import Path
import ast
import hashlib
import re
import subprocess
import sys
import tomllib
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'blender_xr'
manifest=tomllib.loads((SOURCE/'blender_manifest.toml').read_text())
assert manifest['id']=='blender_xr'
assert manifest['name']=='Mesh XR'
assert manifest.get('support')=='https://github.com/dedzedofficial/Blender-XR/issues'
version=manifest['version']

OPENVR_VERSION='2.12.1401'
OPENVR_WHEEL='openvr-'+OPENVR_VERSION+'-py3-none-any.whl'
OPENVR_SHA256='ef761cef3162843a8025a7812d5e244fd94ab3a992ca8f5ef0d1b0188ad56cb3'
WHEELS=SOURCE/'wheels'
wheel_path=WHEELS/OPENVR_WHEEL
expected_wheel='./wheels/'+OPENVR_WHEEL
assert manifest.get('wheels')==[expected_wheel], 'manifest must declare the pinned OpenVR wheel'

# Blender Extensions requires third-party Python libraries to ship as wheels.
# Download the exact upstream PyPI wheel when it is not already present, then
# verify the published checksum so the package cannot silently vendor a changed file.
WHEELS.mkdir(exist_ok=True)
if not wheel_path.is_file():
    subprocess.run([
        sys.executable,'-m','pip','download','openvr=='+OPENVR_VERSION,
        '--only-binary=:all:','--no-deps','--dest',str(WHEELS),
    ],check=True)
assert wheel_path.is_file(), OPENVR_WHEEL+' was not downloaded'
actual_wheel_sha=hashlib.sha256(wheel_path.read_bytes()).hexdigest()
assert actual_wheel_sha==OPENVR_SHA256, 'OpenVR wheel checksum mismatch: '+actual_wheel_sha

# Keep every user-visible version source synchronized.
version_source=(SOURCE/'version.py').read_text()
match=re.search(r'^VERSION\s*=\s*(.+)$',version_source,re.MULTILINE)
assert match, 'version.py must define VERSION'
python_version='.'.join(str(part) for part in ast.literal_eval(match.group(1)))
assert python_version==version, f'manifest {version} != Python {python_version}'
assert (SOURCE/'README.md').read_text().startswith('# Mesh XR v'+version+'\n')
init_text=(SOURCE/'__init__.py').read_text()
assert "'name': 'Mesh XR'" in init_text
assert "bl_label='Mesh XR v'+VERSION_TEXT" in init_text
assert "bl_category='Mesh XR'" in init_text
assert "material_uv.BXR_PT_materials_v060.bl_category='Mesh XR'" in init_text
assert "material_uv.BXR_PT_uv_v060.bl_category='Mesh XR'" in init_text
assert "v056.patch(runtime.Runtime)" in init_text
assert "v060.patch(runtime.Runtime)" in init_text
assert "v071.patch(runtime.Runtime)" in init_text
assert "v075_features.CLASSES" in init_text, 'v0.7.5 workflow features must be registered'
assert "precision_mode" in init_text, 'precision mode setting must be present'
assert "triangle_budget" in init_text, 'asset triangle budget setting must be present'
assert "haptic_feedback" in init_text, 'optional haptic feedback setting must be present'
assert "('haptic', 'VIBRATION', '/output/haptic')" in (SOURCE/'actions.py').read_text(), 'OpenXR haptic output action must be present'
assert "mirror_xr_session" in init_text, 'PC View Mode must use Blender native XR mirroring'
assert "Show VR View on PC" in init_text, 'PC View Mode toggle must be visible in the desktop panel'
assert 'material_uv.CLASSES' in init_text
assert 'Patreon' not in init_text
assert "updates=layout.box()" not in init_text

for required in ('material_uv.py','uv_tools.py','v060.py','v071.py','v075_features.py','steamvr_hand_bridge.py'):
    assert (SOURCE/required).is_file(), required+' is required for the v0.6 package'
menus_text=(SOURCE/'menus.py').read_text()
assert "('MATERIALS','MATERIAL_MENU')" in menus_text
assert "'UV_TRANSFORM'" in menus_text and "'UV_PREVIEW'" in menus_text

drawing_text=(SOURCE/'drawing.py').read_text()
assert "text('MESH XR / '+menus.title(self.page)" in drawing_text
assert 'version.DISPLAY_VERSION' in drawing_text
assert "V0.5.3" not in drawing_text

bridge_text=(SOURCE/'steamvr_hand_bridge.py').read_text()
assert "with_name('site-packages')" in bridge_text
assert "'PYTHONPATH'" in bridge_text
assert 'sys.path' not in bridge_text
assert 'pip install openvr' not in bridge_text

# Blender Extensions review explicitly disallows threading/queue in add-ons.
# Parse imports rather than scanning comments/strings so this cannot false-positive
# on documentation that explains the rule.
for source_path in sorted(SOURCE.glob('*.py')):
    tree=ast.parse(source_path.read_text(),filename=str(source_path))
    for node in ast.walk(tree):
        names=[]
        if isinstance(node,ast.Import):
            names=[alias.name.split('.')[0] for alias in node.names]
        elif isinstance(node,ast.ImportFrom) and node.module:
            names=[node.module.split('.')[0]]
        forbidden={'threading','queue'}.intersection(names)
        assert not forbidden, f'{source_path.name} imports forbidden Blender crasher(s): {sorted(forbidden)}'

output=ROOT/'dist'/('mesh-xr-v'+version+'.zip')
output.parent.mkdir(exist_ok=True)
# Keep the current installer only; source history remains in Git.
for old in output.parent.glob('*xr-v*'):
    if old.name not in {output.name,output.name+'.sha256'}:
        old.unlink()

package_names={'blender_manifest.toml','LICENSE','README.md'}
manifest_wheels={Path(item.removeprefix('./')).as_posix() for item in manifest['wheels']}
with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(SOURCE.rglob('*')):
        if not path.is_file():
            continue
        relative=path.relative_to(SOURCE).as_posix()
        if not (path.suffix=='.py' or relative in package_names or relative in manifest_wheels):
            continue
        item=zipfile.ZipInfo(relative,date_time=(2026,1,1,0,0,0))
        item.compress_type=zipfile.ZIP_DEFLATED
        item.external_attr=0o100644<<16
        archive.writestr(item,path.read_bytes())

with zipfile.ZipFile(output) as archive:
    names=set(archive.namelist())
    assert 'wheels/'+OPENVR_WHEEL in names, 'OpenVR wheel missing from extension ZIP'
    assert 'blender_manifest.toml' in names and '__init__.py' in names

checksum=hashlib.sha256(output.read_bytes()).hexdigest()
Path(str(output)+'.sha256').write_text(checksum+'  '+output.name+'\n')
print(output)
print(checksum)
