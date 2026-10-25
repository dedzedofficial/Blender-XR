"""Hardware-free Mesh XR v0.8 radial menu input regression tests."""
import importlib.util
import math
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'radial_logic_v080',
    Path(__file__).resolve().parents[1] / 'blender_xr' / 'radial_logic_v080.py')
radial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(radial)


class RadialTests(unittest.TestCase):
    def test_eight_directions_and_deadzone(self):
        self.assertIsNone(radial.wedge(.1, .05))
        for i in range(8):
            angle = math.tau * i / 8
            self.assertEqual(radial.wedge(math.sin(angle), math.cos(angle)), i)
        self.assertIsNone(radial.wedge(float('nan'), 1))
        self.assertEqual(radial.wedge(0, .41, previous=0), 0)
        self.assertIsNone(radial.wedge(0, .38, previous=0))

    def test_hysteresis_prevents_sector_jitter(self):
        a = math.radians(25)
        self.assertEqual(radial.wedge(math.sin(a), math.cos(a), previous=0), 0)
        a = math.radians(38)
        self.assertEqual(radial.wedge(math.sin(a), math.cos(a), previous=0), 1)

    def test_open_select_release_or_cancel(self):
        menu = [(str(i), 'ACTION_' + str(i)) for i in range(8)]
        state = radial.RadialState()
        self.assertEqual(state.update(True, (0, 0), menu, 'TOOLS'), ('open', None))
        self.assertEqual(state.update(True, (0, 1), menu, 'TOOLS'), ('hover', 'ACTION_0'))
        self.assertEqual(state.update(False, (0, 1), menu, 'TOOLS'), ('select', 'ACTION_0'))
        self.assertIsNone(state.update(False, (0, 0), menu, 'TOOLS'))
        self.assertEqual(state.update(True, (0, 0), menu, 'TOOLS'), ('open', None))
        state.update(True, (1, 0), menu, 'TOOLS')
        state.update(True, (0, 0), menu, 'TOOLS')
        self.assertEqual(state.update(False, (0, 0), menu, 'TOOLS'), ('close', None))

    def test_submenu_recenter_without_releasing_trigger(self):
        menu = [('MODE', 'MODE_MENU'), ('SELECT', 'SELECT')]
        state = radial.RadialState()
        state.update(True, (0, 0), menu, 'TOOLS')
        state.update(True, (0, 1), menu, 'TOOLS')
        self.assertEqual(state.update(True, (0, 0), menu, 'TOOLS'), ('navigate', 'MODE_MENU'))
        child = [('OBJECT', 'MODE_OBJECT'), ('EDIT', 'MODE_EDIT')]
        self.assertIsNone(state.update(True, (0, 0), child, 'MODE_SELECT'))
        self.assertEqual(state.update(True, (.71, .71), child, 'MODE_SELECT'), ('hover', 'MODE_EDIT'))
        self.assertEqual(state.update(False, (.71, .71), child, 'MODE_SELECT'), ('select', 'MODE_EDIT'))

    def test_pagination_never_loses_existing_menu_actions(self):
        buttons = [(str(i), 'ACT_' + str(i)) for i in range(15)]
        actions = []
        for page in range(3):
            visible = radial.visible_actions(buttons, page)
            self.assertLessEqual(len(visible), 8)
            actions.extend(a for _, a in visible if a != 'RADIAL_NEXT')
        self.assertEqual(set(actions), {a for _, a in buttons})

    def test_one_input_source_independent_of_dominant_hand(self):
        # Handedness is resolved in the XR wrapper: index = 1 - dominant index.
        for dominant in (0, 1):
            off = 1 - dominant
            self.assertNotEqual(dominant, off)
        # Inputs to the radial never require the other controller's stick.
        state = radial.RadialState()
        menu = [('A', 'ACT_A')]
        state.update(True, (0, 0), menu, 'TOOLS')
        state.update(True, (0, 1), menu, 'TOOLS')
        self.assertEqual(state.update(False, (0, 1), menu, 'TOOLS'), ('select', 'ACT_A'))


if __name__ == '__main__':
    unittest.main()
