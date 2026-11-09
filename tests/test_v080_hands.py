"""Blender v0.8 alpha: native add-on settings and articulated hand geometry."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bpy
import blender_xr
from blender_xr import hands_v080, radial_logic_v080, runtime, drawing, version


def main():
    assert version.VERSION == (0, 8, 0)
    blender_xr.register()
    try:
        settings = bpy.context.scene.blender_xr
        assert settings.menu_style == 'RADIAL'
        assert settings.hand_display == 'HANDS'
        assert runtime.Runtime._v080_radial_patched
        assert hasattr(drawing, 'draw')
        original = len(bpy.data.objects)
        open_right = hands_v080.hand_mesh(0, 0, left=False)
        closed_right = hands_v080.hand_mesh(1, 1, left=False)
        open_left = hands_v080.hand_mesh(0, 0, left=True)
        assert len(open_right) > 500
        assert len(open_right) == len(closed_right) == len(open_left)
        assert any((a-b).length > .01 for a, b in zip(open_right, closed_right))
        assert len(bpy.data.objects) == original, 'Visual hands must not create scene objects'
        assert all(all(-.5 < v < .5 for v in point) for point in open_right)
        assert radial_logic_v080.visible_actions([('A','SELECT'),('B','MOVE')]) == [
            ('A', 'SELECT'), ('B', 'MOVE')]
        settings.menu_style = 'CLASSIC'
        settings.hand_display = 'CONTROLLERS'
        assert settings.menu_style == 'CLASSIC'
        print('PASS v0.8 articulated GPU-only hands, settings and radial module')
    finally:
        blender_xr.unregister()


if __name__ == '__main__':
    main()
