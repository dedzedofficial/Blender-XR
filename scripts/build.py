"""Build a root-layout Blender extension ZIP and checksum from source."""
from pathlib import Path
import ast
import hashlib
import re
import tomllib
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'blender_xr'
manifest=tomllib.loads((SOURCE/'blender_manifest.toml').read_text())
assert manifest['id']=='blender_xr'
assert manifest['name']=='XR Mesh'
version=manifest['version']

# Keep every user-visible version source synchronized. This specifically guards
# against the old situation where the manifest had advanced but the VR footer
# and packaged README still advertised an older release/name.
version_source=(SOURCE/'version.py').read_text()
match=re.search(r'^VERSION\s*=\s*(.+)$',version_source,re.MULTILINE)
assert match, 'version.py must define VERSION'
python_version='.'.join(str(part) for part in ast.literal_eval(match.group(1)))
assert python_version==version, f'manifest {version} != Python {python_version}'
assert (SOURCE/'README.md').read_text().startswith('# XR Mesh v'+version+'\n')
init_text=(SOURCE/'__init__.py').read_text()
assert "'version': VERSION" in init_text
assert "'name': 'XR Mesh'" in init_text
assert "bl_label='XR Mesh v'+VERSION_TEXT" in init_text
drawing_text=(SOURCE/'drawing.py').read_text()
assert 'version.DISPLAY_VERSION' in drawing_text
assert "text('XR MESH / '+menus.title(self.page)" in drawing_text
assert "V0.5.3" not in drawing_text

# Blender Extensions policy: these modules are unsafe in an in-process add-on.
# Keep this check broad enough to reject normal imports without flagging docs.
for source in SOURCE.glob('*.py'):
    text=source.read_text()
    assert not re.search(r'^\s*(?:from\s+(?:threading|queue)\b|import\s+(?:threading|queue)\b)', text, re.MULTILINE), \
        f'{source.name}: threading/queue are not allowed'

output=ROOT/'dist'/('blender-xr-v'+version+'.zip')
output.parent.mkdir(exist_ok=True)
# Keep the current installer only; source history remains in Git.
for old in output.parent.glob('blender-xr-v*'):
    if old.name not in {output.name,output.name+'.sha256'}:
        old.unlink()
with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(SOURCE.iterdir()):
        if path.is_file() and (path.suffix=='.py' or path.name in {'blender_manifest.toml','LICENSE','README.md'}):
            item=zipfile.ZipInfo(path.name,date_time=(2026,1,1,0,0,0))
            item.compress_type=zipfile.ZIP_DEFLATED
            item.external_attr=0o100644<<16
            archive.writestr(item,path.read_bytes())
checksum=hashlib.sha256(output.read_bytes()).hexdigest()
Path(str(output)+'.sha256').write_text(checksum+'  '+output.name+'\n')
print(output)
print(checksum)
