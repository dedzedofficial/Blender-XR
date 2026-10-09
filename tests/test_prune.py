"""Never prune downloads until the current release bytes are verified."""
import hashlib,importlib.util,json,os,tempfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('prune',Path(__file__).resolve().parents[1]/'scripts/prune_releases.py')
prune=importlib.util.module_from_spec(spec);spec.loader.exec_module(prune)
with tempfile.TemporaryDirectory() as folder:
    prune.ROOT=Path(folder)
    (prune.ROOT/'blender_xr').mkdir();(prune.ROOT/'dist').mkdir()
    (prune.ROOT/'blender_xr/blender_manifest.toml').write_text('version="0.4.4"')
    installer='blender-xr-v0.4.4.zip';payload=b'verified test installer'
    (prune.ROOT/'dist'/installer).write_bytes(payload)
    os.environ['GITHUB_REPOSITORY']='example/test';os.environ['GITHUB_SHA']='current'
    calls=[];corrupt=[False]
    def gh(*args):
        calls.append(args)
        if args[:2]==('release','download'):
            target=Path(args[args.index('--dir')+1]);data=b'corrupt' if corrupt[0] else payload
            (target/installer).write_bytes(data)
            (target/(installer+'.sha256')).write_text(hashlib.sha256(payload).hexdigest()+'  '+installer)
        elif args[:2]==('release','list'):
            return json.dumps([{'tagName':v} for v in ['v0.4.3','v0.4.4','v0.4.5','other']])
        elif args[:3]==('api','--paginate','--slurp'):
            return json.dumps([{'artifacts':[{'id':1,'name':'blender-xr-old','workflow_run':{'head_sha':'old'}},{'id':2,'name':'blender-xr-current','workflow_run':{'head_sha':'current'}},{'id':3,'name':'other','workflow_run':{'head_sha':'old'}}]}])
        return ''
    prune.gh=gh
    prune.main()
    assert [c[2] for c in calls if c[:2]==('release','delete')]==['v0.4.3']
    assert [c[-1] for c in calls if c[:3]==('api','--method','DELETE')]==['repos/example/test/actions/artifacts/1']
    calls.clear();corrupt[0]=True
    try:prune.main()
    except RuntimeError:pass
    else:raise AssertionError('Corrupt release was allowed')
    assert not any(c[:2]==('release','delete') or c[:3]==('api','--method','DELETE') for c in calls)
print('PASS verified release pruning and corrupt-release retention')
