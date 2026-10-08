# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional external helper. Run with system Python, not Blender's bundled Python."""
import argparse
import json
import math
from pathlib import Path
import socket
import tempfile
import time


def manifests(folder):
    actions = [{'name': '/actions/bxr/in/' + side, 'type': 'skeleton',
                'skeleton': '/skeleton/hand/' + side} for side in ('left', 'right')]
    defaults = []
    # SteamVR Input can rebind these actions for other skeletal input providers.
    for controller in ('knuckles', 'oculus_touch'):
        filename = controller + '.json'
        defaults.append({'controller_type': controller, 'binding_url': filename})
        binding = {'controller_type': controller, 'name': 'Blender XR finger input',
                   'description': 'Experimental skeletal input bridge',
                   'bindings': {'/actions/bxr': {'skeleton': [
                       {'output': '/actions/bxr/in/' + side,
                        'path': '/user/hand/' + side + '/input/skeleton/' + side}
                       for side in ('left', 'right')]}}}
        (folder / filename).write_text(json.dumps(binding))
    manifest = {'action_sets': [{'name': '/actions/bxr', 'usage': 'leftright'}],
                'actions': actions, 'default_bindings': defaults}
    path = folder / 'actions.json'
    path.write_text(json.dumps(manifest))
    return path


def sample(vr, inputs, handle):
    active = inputs.getSkeletalActionData(handle).bActive
    level = inputs.getSkeletalTrackingLevel(handle)
    levels = {vr.VRSkeletalTracking_Partial: 'partial', vr.VRSkeletalTracking_Full: 'full'}
    if not active or level not in levels:
        return {'tracked': False, 'level': 'estimated', 'pinch': 0.1, 'curl': 0.0}
    count = inputs.getBoneCount(handle)
    if count < 26:
        raise ValueError('SteamVR hand skeleton has too few bones')
    bones = (vr.VRBoneTransform_t * count)()
    inputs.getSkeletalBoneData(handle, vr.VRSkeletalTransformSpace_Model,
                              vr.VRSkeletalMotionRange_WithoutController, bones)
    # SteamVR standard hand skeleton: thumb tip 5, index tip 10.
    a, b = bones[5].position.v, bones[10].position.v
    pinch = math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))
    summary = inputs.getSkeletalSummaryData(handle, vr.VRSummaryType_FromAnimation)
    curl = sum(summary.flFingerCurl[i] for i in (2, 3, 4)) / 3
    return {'tracked': True, 'level': levels[level], 'pinch': pinch, 'curl': curl}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key', required=True, help='Session key shown in Blender XR')
    parser.add_argument('--port', type=int, default=39540)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535')
    try:
        import openvr
    except ImportError:
        parser.exit(1, 'Install the optional helper dependency: python -m pip install openvr==2.12.1401\n')
    print('Starting experimental hand bridge. Use SteamVR OpenXR, release both hands to arm.')
    initialized = False
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        openvr.init(openvr.VRApplication_Background)
        initialized = True
        inputs = openvr.VRInput()
        with tempfile.TemporaryDirectory(prefix='blender-xr-hands-') as temporary:
            inputs.setActionManifestPath(str(manifests(Path(temporary)).resolve()))
            active = (openvr.VRActiveActionSet_t * 1)()
            active[0].ulActionSet = inputs.getActionSetHandle('/actions/bxr')
            handles = [inputs.getActionHandle('/actions/bxr/in/' + side) for side in ('left', 'right')]
            seq = time.monotonic_ns()
            last_error = ''
            while True:
                try:
                    inputs.updateActionState(active)
                    hands = [sample(openvr, inputs, handle) for handle in handles]
                    last_error = ''
                except Exception as exc:
                    if str(exc) != last_error:
                        print('Hand input unavailable:', exc, flush=True)
                        last_error = str(exc)
                    hands = [{'tracked': False} for _ in handles]
                data = {'v': 1, 'key': args.key, 'seq': seq, 'hands': hands}
                sock.sendto(json.dumps(data).encode(), ('127.0.0.1', args.port))
                seq += 1
                time.sleep(1 / 60)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        parser.exit(1, 'SteamVR bridge could not start: ' + str(exc) + '\n')
    finally:
        sock.close()
        if initialized:
            openvr.shutdown()


if __name__ == '__main__':
    main()
