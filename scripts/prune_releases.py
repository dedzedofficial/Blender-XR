"""Keep only the verified current installer release; executed by release CI."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import tomllib

ROOT=Path(__file__).resolve().parents[1]
def gh(*arguments):
    return subprocess.check_output(['gh',*arguments],text=True)

def version(tag):
    match=re.fullmatch(r'v(\d+)\.(\d+)\.(\d+)',tag)
    return tuple(map(int,match.groups())) if match else None


def main():
    manifest=tomllib.loads((ROOT/'blender_xr/blender_manifest.toml').read_text())
    current='v'+manifest['version']
    installer='blender-xr-'+current+'.zip'
    repository=os.environ['GITHUB_REPOSITORY']
    sha=os.environ['GITHUB_SHA']
    # Verify published bytes before deleting any prior downloadable version.
    with tempfile.TemporaryDirectory() as folder:
        gh('release','download',current,'--repo',repository,'--dir',folder,
           '--pattern',installer,'--pattern',installer+'.sha256')
        check=(Path(folder)/(installer+'.sha256')).read_text().split()
        digest=hashlib.sha256((Path(folder)/installer).read_bytes()).hexdigest()
        local_digest=hashlib.sha256((ROOT/'dist'/installer).read_bytes()).hexdigest()
        if len(check)!=2 or check[1]!=installer or check[0]!=digest or digest!=local_digest:
            raise RuntimeError('Current release verification failed; older releases retained')
    releases=json.loads(gh('release','list','--repo',repository,'--limit','1000','--json','tagName'))
    for release in releases:
        tag=release['tagName']
        if version(tag) is not None and version(tag)<version(current):
            print('Remove older release',tag,flush=True)
            gh('release','delete',tag,'--repo',repository,'--yes','--cleanup-tag')
    # Installer artifacts from previous commits are older downloads as well.
    pages=json.loads(gh('api','--paginate','--slurp','repos/'+repository+'/actions/artifacts'))
    for page in pages:
        for artifact in page.get('artifacts',[]):
            if (artifact['name'].startswith('blender-xr-') and
                    artifact.get('workflow_run',{}).get('head_sha') != sha):
                print('Remove older installer artifact',artifact['id'],flush=True)
                gh('api','--method','DELETE','repos/'+repository+'/actions/artifacts/'+str(artifact['id']))
    print('Only current Blender XR release downloads retained:',current)

if __name__=='__main__':
    main()
