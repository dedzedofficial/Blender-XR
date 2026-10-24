"""Blender-side smoke coverage for Mesh XR's 0.7.6 compact sidebar."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bpy
import blender_xr
from blender_xr import material_uv, ui_v076, v075_features, version


class FakeLayout:
    def __init__(self, root=None):
        self.root = root or self
        if root is None:
            self.calls = []
        self.enabled = True
        self.scale_y = 1.0

    def row(self, **_kwargs):
        return FakeLayout(self.root)

    def column(self, **_kwargs):
        return FakeLayout(self.root)

    def box(self):
        return FakeLayout(self.root)

    def prop(self, _data, property_name, **kwargs):
        self.root.calls.append(('prop', property_name, kwargs))
        return None

    def label(self, **kwargs):
        self.root.calls.append(('label', kwargs.get('text', ''), kwargs.get('icon')))

    def operator(self, identifier, **kwargs):
        self.root.calls.append(('operator', identifier, kwargs))
        return SimpleNamespace()

    def separator(self):
        self.root.calls.append(('separator',))


def test():
    assert version.VERSION == (0, 7, 6), version.VERSION
    assert len(ui_v076.UI_SECTION_ITEMS) == 7
    assert len({item[0] for item in ui_v076.UI_SECTION_ITEMS}) == 7
    assert all(item[3] for item in ui_v076.UI_SECTION_ITEMS), 'Every workspace requires a Blender icon'
    assert blender_xr.BXR_PT_panel.bl_idname == 'BXR_PT_panel'
    assert material_uv.BXR_PT_materials_v060.bl_parent_id == 'BXR_PT_panel'
    assert material_uv.BXR_PT_uv_v060.bl_parent_id == 'BXR_PT_panel'
    assert v075_features.BXR_PT_workflow.bl_parent_id == 'BXR_PT_panel'

    blender_xr.register()
    try:
        settings = bpy.context.scene.blender_xr
        expected = {
            'SESSION': 'blender_xr.session',
            'MODEL': 'blender_xr.asset_audit',
            'MATERIAL': 'blender_xr.apply_color',
            'TRAVEL': None,
            'PROJECT': 'blender_xr.save',
            'HELP': 'wm.search_menu',
        }
        try:
            for section in (item[0] for item in ui_v076.UI_SECTION_ITEMS):
                settings.ui_section = section
                fake = FakeLayout()
                ui_v076.draw_panel(SimpleNamespace(layout=fake), bpy.context)
                assert any(item[0] == 'prop' and item[1] == 'ui_section'
                           for item in fake.calls), section
                expected_operator = expected.get(section)
                if expected_operator:
                    assert any(item[0] == 'operator' and item[1] == expected_operator
                               for item in fake.calls), section
                assert any(item[0] == 'label' for item in fake.calls), section
        finally:
            settings.ui_section = 'SESSION'
    finally:
        blender_xr.unregister()
    print('PASS 0.7.6 icon workspaces, operator routes and nested advanced panels')


if __name__ == '__main__':
    test()
