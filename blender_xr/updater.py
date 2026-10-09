# SPDX-License-Identifier: GPL-3.0-or-later
"""HTTPS release updater. Network runs off Blender's main thread."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import threading
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import bpy
from bpy.props import StringProperty

REPOSITORY='dedzedofficial/Blender-XR'
API='https://api.github.com/repos/'+REPOSITORY
VERSION=(0,4,3)
MAX_BYTES=16*1024*1024
JOB=None
LATEST=None
STOPPED=False


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        parsed=urllib.parse.urlparse(newurl)
        if parsed.scheme!='https' or not (
            parsed.hostname in {'api.github.com','github.com','objects.githubusercontent.com','release-assets.githubusercontent.com'}):
            raise ValueError('GitHub redirected to an unsupported download host')
        redirected=super().redirect_request(req,fp,code,msg,headers,newurl)
        if redirected and parsed.hostname!='api.github.com':
            redirected.remove_header('Authorization')
        return redirected


def request(url,token='',binary=False):
    if not bpy.app.online_access:
        raise ValueError('Enable Allow Online Access in Blender preferences to check updates')
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme!='https' or parsed.hostname!='api.github.com':
        raise ValueError('Only official GitHub API requests are allowed')
    headers={'User-Agent':'DedZed-Blender-XR/0.4','Accept':
             'application/octet-stream' if binary else 'application/vnd.github+json',
             'X-GitHub-Api-Version':'2022-11-28'}
    if token:
        headers['Authorization']='Bearer '+token
    req=urllib.request.Request(url,headers=headers)
    with urllib.request.build_opener(SafeRedirect()).open(req,timeout=30) as response:
        length=response.headers.get('Content-Length')
        if length and int(length)>MAX_BYTES:
            raise ValueError('Release file is larger than the updater limit')
        data=response.read(MAX_BYTES+1)
        if len(data)>MAX_BYTES:
            raise ValueError('Release file is larger than the updater limit')
        return data


def version(tag):
    match=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)',tag)
    if not match:
        raise ValueError('Release tag must use vMAJOR.MINOR.PATCH')
    return tuple(int(n) for n in match.groups())


def latest(token):
    release=json.loads(request(API+'/releases/latest',token))
    if release.get('draft') or release.get('prerelease'):
        raise ValueError('The latest release is not a stable release')
    v=version(release['tag_name'])
    expected='blender-xr-v'+'.'.join(map(str,v))+'.zip'
    assets={a['name']:a for a in release.get('assets',[])}
    if expected not in assets or expected+'.sha256' not in assets:
        raise ValueError('Latest release is missing the installer or checksum')
    return {'version':v,'name':expected,'asset':assets[expected],
            'checksum':assets[expected+'.sha256']}


def validate_archive(data,expected_version):
    """No extraction of user-controlled paths, links, or oversized archives."""
    files={}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        total=0
        for info in archive.infolist():
            name=info.filename
            path=PurePosixPath(name)
            if ('\\' in name or path.is_absolute() or '..' in path.parts or
                len(path.parts)!=1 or name in files or
                (info.external_attr>>16)&0o170000==0o120000):
                raise ValueError('Unsafe path or symbolic link in release ZIP')
            if info.is_dir():
                raise ValueError('Installer ZIP must contain files at its root')
            total+=info.file_size
            if total>MAX_BYTES or len(files)>=64:
                raise ValueError('Installer ZIP exceeds safe size limits')
            files[name]=archive.read(info)
    required={'__init__.py','blender_manifest.toml','actions.py','drawing.py',
              'mesh.py','runtime.py','updater.py','gestures.py',
              'primitives.py','project.py','steamvr_hand_bridge.py','LICENSE'}
    if not required.issubset(files):
        raise ValueError('Release ZIP is missing required add-on files')
    if any(not (name.endswith('.py') or name in {'blender_manifest.toml','LICENSE','README.md'})
           for name in files):
        raise ValueError('Release ZIP contains an unexpected file type')
    manifest=tomllib.loads(files['blender_manifest.toml'].decode())
    if manifest['id']!='blender_xr' or version(manifest['version'])!=expected_version:
        raise ValueError('Release ZIP identity or version does not match the release')
    if version(manifest['blender_version_min'])>bpy.app.version[:3]:
        raise ValueError('This update requires a newer Blender version')
    for name,content in files.items():
        if name.endswith('.py'):
            compile(content,name,'exec')
    return files


def download(release,token):
    data=request(release['asset']['url'],token,True)
    check=request(release['checksum']['url'],token,True).decode().strip().split()
    if not check or not re.fullmatch('[a-fA-F0-9]{64}',check[0]):
        raise ValueError('Invalid release checksum')
    if len(check)>1 and check[1].lstrip('*')!=release['name']:
        raise ValueError('Checksum references another installer')
    if hashlib.sha256(data).hexdigest()!=check[0].lower():
        raise ValueError('Release checksum verification failed')
    validate_archive(data,release['version'])
    fd,path=tempfile.mkstemp(prefix='blender-xr-',suffix='.zip')
    with os.fdopen(fd,'wb') as output:output.write(data)
    return path


def install(path,expected_version,destination=None):
    root=Path(destination) if destination else Path(__file__).resolve().parent
    files=validate_archive(Path(path).read_bytes(),expected_version)
    if not (root/'blender_manifest.toml').is_file():
        raise ValueError('Cannot identify the installed Blender XR directory')
    # Stage all bytes and a complete backup before replacing any installed file.
    backup=Path(tempfile.mkdtemp(prefix='.blender-xr-backup-',dir=root.parent))
    staging=Path(tempfile.mkdtemp(prefix='.blender-xr-stage-',dir=root.parent))
    touched=[]
    success=False
    rolled_back=False
    try:
        for name,data in files.items():
            (staging/name).write_bytes(data)
            if (root/name).exists():
                shutil.copy2(root/name,backup/name)
        for name in files:
            os.replace(staging/name,root/name)
            touched.append(name)
        cache=root/'__pycache__'
        if cache.exists():shutil.rmtree(cache,ignore_errors=True)
        success=True
    except Exception:
        for name in reversed(touched):
            old=backup/name
            if old.exists():os.replace(old,root/name)
            else:(root/name).unlink(missing_ok=True)
        rolled_back=True
        raise
    finally:
        shutil.rmtree(staging,ignore_errors=True)
        # Keep the backup if rollback itself fails.
        if success or rolled_back or not touched:
            shutil.rmtree(backup,ignore_errors=True)
    return True


def worker(job,mode,token):
    try:
        release=latest(token)
        job['release']=release
        if release['version']>VERSION and mode=='INSTALL':
            job['path']=download(release,token)
    except urllib.error.HTTPError as exc:
        job['error']=('Private repository access or a published release is missing (GitHub '+
                      str(exc.code)+'). Check your token and repository releases.')
    except Exception:
        # Never expose URLs, Authorization headers, or token-bearing exception text.
        job['error']='Update failed. Check online access, network, release files, and Blender version.'
    finally:
        job['done']=True


def poll_job():
    global JOB,LATEST
    if JOB is None:return None
    if not JOB.get('done'):return 0.25
    job,JOB=JOB,None
    if STOPPED:
        if job.get('path'):Path(job['path']).unlink(missing_ok=True)
        return None
    settings=bpy.context.window_manager.blender_xr_update
    if job.get('error'):
        settings.status=job['error']
        return None
    LATEST=job['release']
    v=LATEST['version']
    if v<=VERSION:
        settings.status='Blender XR v0.4.3 is up to date'
    elif job.get('path'):
        from . import runtime
        try:
            if runtime.CURRENT or bpy.context.window_manager.xr_session_state and bpy.context.window_manager.xr_session_state.is_running(bpy.context):
                raise ValueError('Stop VR before installing updates')
            install(job['path'],v)
            settings.restart_required=True
            settings.status='Update installed. Restart Blender to use v'+'.'.join(map(str,v))
        except Exception:
            settings.status='Update could not be installed. Stop VR and check folder write permissions.'
        finally:
            Path(job['path']).unlink(missing_ok=True)
    else:
        settings.status='Available: v'+'.'.join(map(str,v))+' - click Download & Install'
    return None


class BXR_UpdateSettings(bpy.types.PropertyGroup):
    token: StringProperty(name='GitHub token',subtype='PASSWORD',options={'SKIP_SAVE'},
        description='Session only: fine-grained GitHub token with Contents read permission for Blender-XR')
    status: StringProperty(default='Updates from dedzedofficial/Blender-XR',options={'SKIP_SAVE'})
    restart_required: bpy.props.BoolProperty(default=False,options={'SKIP_SAVE'})


class BXR_OT_update(bpy.types.Operator):
    bl_idname='blender_xr.update'
    bl_label='Check for Updates'
    mode: bpy.props.EnumProperty(items=[('CHECK','Check',''),('INSTALL','Install','')],default='CHECK')
    def execute(self,context):
        global JOB
        from . import runtime
        settings=context.window_manager.blender_xr_update
        if JOB:
            self.report({'INFO'},'An update check is already running')
            return {'CANCELLED'}
        if settings.restart_required:
            self.report({'INFO'},'Restart Blender before checking again')
            return {'CANCELLED'}
        if runtime.CURRENT:
            self.report({'ERROR'},'Stop VR before checking or installing updates')
            return {'CANCELLED'}
        if not bpy.app.online_access:
            self.report({'ERROR'},'Enable Allow Online Access in Blender preferences')
            return {'CANCELLED'}
        token=settings.token.strip() or os.environ.get('BLENDER_XR_GITHUB_TOKEN','').strip()
        JOB={'done':False}
        settings.status='Checking GitHub...' if self.mode=='CHECK' else 'Downloading update...'
        threading.Thread(target=worker,args=(JOB,self.mode,token),daemon=True).start()
        bpy.app.timers.register(poll_job,first_interval=0.25)
        return {'FINISHED'}


def register():
    global STOPPED
    STOPPED=False
    bpy.utils.register_class(BXR_UpdateSettings)
    bpy.utils.register_class(BXR_OT_update)
    bpy.types.WindowManager.blender_xr_update=bpy.props.PointerProperty(type=BXR_UpdateSettings)


def unregister():
    global STOPPED
    STOPPED=True
    if JOB is None and bpy.app.timers.is_registered(poll_job):
        bpy.app.timers.unregister(poll_job)
    del bpy.types.WindowManager.blender_xr_update
    bpy.utils.unregister_class(BXR_OT_update)
    bpy.utils.unregister_class(BXR_UpdateSettings)
