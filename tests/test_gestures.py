"""Hardware-free protocol, gesture, profile, and SteamVR helper regression tests."""
import ctypes
import importlib.util
import json
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace as NS
import unittest

ROOT = Path(__file__).resolve().parents[1]
def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'blender_xr' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

g = module('gestures')
actions = module('actions')
helper = module('steamvr_hand_bridge')

class Collection(list):
    def new(self, name, *args, **kwargs):
        result = NS(name=name, user_paths=Collection(), bindings=Collection(),
                    component_paths=Collection(), actionmap_items=Collection())
        self.append(result)
        return result

class Tests(unittest.TestCase):
    def test_hold_fires_once_and_rearms(self):
        hold = g.HoldGesture()
        self.assertFalse(hold.update(True, 1))
        self.assertFalse(hold.update(True, 1.6))
        self.assertTrue(hold.update(True, 1.8))
        self.assertFalse(hold.update(True, 3))
        self.assertFalse(hold.update(False, 4))
        self.assertFalse(hold.update(True, 5))
        self.assertTrue(hold.update(True, 5.8))

    def test_udp_auth_hysteresis_loss_and_release_arming(self):
        clock = [0.0]
        bridge = g.HandBridge(0, lambda: clock[0])
        self.addCleanup(bridge.close)
        def packet(seq, pinch=.08, curl=.0, **changes):
            data = dict(v=1, key=bridge.key, seq=seq, hands=[
                dict(tracked=True, level='partial', pinch=pinch, curl=curl) for _ in range(2)])
            data.update(changes)
            return json.dumps(data).encode()
        local = ('127.0.0.1', 1234)
        self.assertFalse(bridge.accept(packet(0), ('10.0.0.1', 1234)))
        self.assertFalse(bridge.accept(packet(0, key='wrong'), local))
        self.assertFalse(bridge.accept(packet(0, pinch=float('nan')), local))
        self.assertFalse(bridge.accept(packet(0, hands=[{}]), local))
        self.assertFalse(bridge.accept(b'[' * 2049, local))
        self.assertTrue(bridge.accept(packet(0, pinch=.01), local))
        self.assertIsNone(bridge.read())  # initially held hands cannot start edits
        self.assertTrue(bridge.accept(packet(1), local))
        self.assertEqual(bridge.read(), ((0.,0.),(0.,0.)))
        self.assertFalse(bridge.accept(packet(1), local))  # replay
        self.assertTrue(bridge.accept(packet(2, pinch=.02, curl=.8), local))
        self.assertEqual(bridge.read(), ((1.,1.),(1.,1.)))
        self.assertTrue(bridge.accept(packet(3, pinch=.03, curl=.6), local))
        self.assertEqual(bridge.read(), ((1.,1.),(1.,1.)))
        clock[0] = .3
        self.assertIsNone(bridge.read())  # loss does not emit a release/commit
        self.assertTrue(bridge.accept(packet(4, pinch=.01), local))
        self.assertIsNone(bridge.read())
        self.assertTrue(bridge.accept(packet(5), local))
        self.assertEqual(bridge.read(), ((0.,0.),(0.,0.)))
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(sender.close)
        sender.sendto(packet(6, pinch=.01), ('127.0.0.1', bridge.port))
        self.assertEqual(bridge.read(), ((1.,0.),(1.,0.)))
        self.assertFalse(bridge.accept(packet(7, hands=[dict(tracked=True, level='estimated', pinch=.1, curl=0)]*2), local))

    def test_profiles_and_optional_touch(self):
        for family, expected in [('META', {'touch', 'simple'}),
                                 ('VALVE', {'touch','index','vive','simple'}),
                                 ('AUTO', {'touch','index','vive','simple'})]:
            state = NS(actionmaps=NS(new=lambda *a, **k: NS(actionmap_items=Collection())))
            amap = actions.build_map(state, family, True)
            self.assertEqual(len(amap.actionmap_items), 8)
            for item in amap.actionmap_items:
                self.assertEqual([p.name for p in item.user_paths], list(actions.HANDS))
                keys = {b.name for b in item.bindings}
                if item.name.endswith('_touch'):
                    self.assertEqual(keys, expected & {'touch','index'})
                elif item.name in ('grab','stick','boost'):
                    self.assertEqual(keys, expected - {'simple'})
                else:
                    self.assertEqual(keys, expected)
                for binding in item.bindings:
                    self.assertEqual(len(binding.component_paths), 2)
                    self.assertTrue(all(p.name.startswith('/input/') for p in binding.component_paths))

    def test_helper_manifest_and_skeletal_measurements(self):
        with tempfile.TemporaryDirectory() as folder:
            path = helper.manifests(Path(folder))
            data = json.loads(path.read_text())
            self.assertEqual(len(data['actions']), 2)
            for default in data['default_bindings']:
                binding = json.loads((Path(folder)/default['binding_url']).read_text())
                self.assertEqual(len(binding['bindings']['/actions/bxr']['skeleton']),2)
        class Vec(ctypes.Structure):
            _fields_ = [('v',ctypes.c_float*4)]
        class Bone(ctypes.Structure):
            _fields_ = [('position',Vec)]
        vr = NS(VRSkeletalTracking_Partial=1,VRSkeletalTracking_Full=2,
                VRBoneTransform_t=Bone,VRSkeletalTransformSpace_Model=0,
                VRSkeletalMotionRange_WithoutController=1,VRSummaryType_FromAnimation=0)
        def bone_data(handle, space, motion, bones):
            bones[10].position.v[0] = .02
        inputs = NS(getSkeletalActionData=lambda h:NS(bActive=True),
                    getSkeletalTrackingLevel=lambda h:1,getBoneCount=lambda h:31,
                    getSkeletalBoneData=bone_data,
                    getSkeletalSummaryData=lambda h, kind:NS(flFingerCurl=[0,0,.6,.8,1]))
        result = helper.sample(vr,inputs,1)
        self.assertAlmostEqual(result['pinch'], .02)
        self.assertAlmostEqual(result['curl'], .8)
        self.assertEqual(result['level'],'partial')
        inputs.getSkeletalTrackingLevel = lambda h:0
        self.assertFalse(helper.sample(vr,inputs,1)['tracked'])

if __name__ == '__main__':
    unittest.main()
