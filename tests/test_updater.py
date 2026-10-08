import sys,io,zipfile,tempfile,shutil,tomllib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from blender_xr import updater
ROOT=Path(__file__).resolve().parents[1]
version=tuple(map(int,tomllib.loads((ROOT/'blender_xr/blender_manifest.toml').read_text())['version'].split('.')))
archive=ROOT/'dist'/('blender-xr-v'+'.'.join(map(str,version))+'.zip')
data=archive.read_bytes()
files=updater.validate_archive(data,version)
assert 'runtime.py' in files
for name in ['../evil.py','/evil.py','nested/file.py','bad\\file.py']:
    payload=io.BytesIO()
    with zipfile.ZipFile(payload,'w') as z:z.writestr(name,b'bad')
    try:updater.validate_archive(payload.getvalue(),version)
    except ValueError:pass
    else:raise AssertionError('Unsafe path allowed: '+name)
try:updater.validate_archive(data,(9,9,9))
except ValueError:pass
else:raise AssertionError('Wrong release version accepted')
with tempfile.TemporaryDirectory() as work:
    root=Path(work)/'blender_xr';shutil.copytree(ROOT/'blender_xr',root)
    updater.install(archive,version,root)
    assert (root/'__init__.py').read_bytes()==files['__init__.py']
    old={p.name:p.read_bytes() for p in root.iterdir() if p.is_file()}
    real_replace=updater.os.replace
    calls=[0]
    def fail_once(a,b):
        calls[0]+=1
        if calls[0]==3:raise OSError('Simulated write failure')
        return real_replace(a,b)
    updater.os.replace=fail_once
    try:
        try:updater.install(archive,version,root)
        except OSError:pass
        else:raise AssertionError('Simulated install failure was ignored')
    finally:updater.os.replace=real_replace
    assert old=={p.name:p.read_bytes() for p in root.iterdir() if p.is_file()}
from urllib.request import Request
req=Request('https://api.github.com/release',headers={'Authorization':'Bearer test-only'})
redirect=updater.SafeRedirect().redirect_request(req,None,302,'',{},'https://release-assets.githubusercontent.com/download')
assert not redirect.has_header('Authorization')
try:updater.SafeRedirect().redirect_request(req,None,302,'',{},'https://example.com/download')
except ValueError:pass
else:raise AssertionError('Unexpected redirect host allowed')
print('PASS release ZIP, unsafe paths, identity/version, install rollback, token-safe redirects')
