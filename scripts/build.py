"""Build a root-layout Blender extension ZIP and checksum from source."""
from pathlib import Path
import hashlib
import tomllib
import zipfile
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'blender_xr'
manifest=tomllib.loads((SOURCE/'blender_manifest.toml').read_text())
assert manifest['id']=='blender_xr'
version=manifest['version']
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
