"""Blender-side smoke coverage for Mesh XR's 0.7.6 compact sidebar."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bpy
import blender_xr
from blender_xr import drawing, material_uv, menus, ui_v076, v065, v075_features, version


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
    # Blender validates the actual icon vocabulary, not just nonempty strings.
    valid_icons = {
        item.identifier for item in
        bpy.types.UILayout.bl_rna.functions['label'].parameters['icon'].enum_items
    }
    assert valid_icons, "Could not retrieve Blender's native icon identifiers"
    import ast
    icon_sources = ('ui_v076.py', 'material_uv.py', 'v075_features.py')
    requested_icons = {item[3] for item in ui_v076.UI_SECTION_ITEMS}
    for source_name in icon_sources:
        code = Path(blender_xr.__file__).parent / source_name
        for node in ast.walk(ast.parse(code.read_text(encoding='utf-8'))):
            if not isinstance(node, ast.Call):
                continue
            for option in node.keywords:
                if option.arg == 'icon' and isinstance(option.value, ast.Constant):
                    if isinstance(option.value.value, str):
                        requested_icons.add(option.value.value)
    missing_native_icons = requested_icons.difference(valid_icons)
    assert not missing_native_icons, 'Invalid native Blender icons: ' + ', '.join(sorted(missing_native_icons))
    for key, label, _description, icon, _order in ui_v076.UI_SECTION_ITEMS:
        assert icon in valid_icons, (key, icon)
    for page, buttons in menus.PAGES.items():
        assert buttons, 'Empty VR page: ' + page
        for _label, action in buttons:
            if action == 'PANEL':
                assert page == 'MATERIAL_ADJUST', 'Blank slots are only allowed for HSL sliders'
                continue
            assert drawing._ICON_BY_ACTION.get(action), (page, action)
            source = drawing._ICON_BY_ACTION[action]
            icon_file = Path(drawing.__file__).parent / 'icons' / (source + '.png')
            assert icon_file.is_file(), (page, action, source)
    # The core overlay must not repaint button backgrounds on top of textures.
    import inspect
    assert "0.0025" not in inspect.getsource(v065._patch_menu_draw)
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
                for call in fake.calls:
                    if call[0] == 'operator':
                        assert call[2].get('icon') in valid_icons, (section, call)
                    elif call[0] == 'prop':
                        if call[1] == 'ui_section':
                            assert call[2].get('icon_only') is True
                        else:
                            assert call[2].get('icon') in valid_icons, (section, call)
                    elif call[0] == 'label' and call[1] and not str(call[1]).isdigit():
                        assert call[2] in valid_icons, (section, call)
            # Check nested advanced panels, not just the seven top-level pages.
            bpy.ops.object.mode_set(mode='OBJECT') if bpy.context.object and bpy.context.object.mode != 'OBJECT' else None
            bpy.ops.mesh.primitive_cube_add()
            obj = bpy.context.object
            for panel_type in (material_uv.BXR_PT_materials_v060, v075_features.BXR_PT_workflow):
                fake = FakeLayout()
                panel_type.draw(SimpleNamespace(layout=fake), bpy.context)
                for call in fake.calls:
                    if call[0] == 'operator':
                        assert call[2].get('icon') in valid_icons, (panel_type.__name__, call)
                    elif call[0] == 'prop':
                        assert call[2].get('icon') in valid_icons, (panel_type.__name__, call)
            bpy.ops.object.mode_set(mode='EDIT')
            fake = FakeLayout()
            material_uv.BXR_PT_uv_v060.draw(SimpleNamespace(layout=fake), bpy.context)
            for call in fake.calls:
                if call[0] == 'operator':
                    assert call[2].get('icon') in valid_icons, ('UV', call)
                elif call[0] == 'prop':
                    assert call[2].get('icon') in valid_icons, ('UV', call)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.data.objects.remove(obj, do_unlink=True)
        finally:
            settings.ui_section = 'SESSION'
    finally:
        blender_xr.unregister()
    print('PASS 0.7.6 icon workspaces, operator routes and nested advanced panels')


if __name__ == '__main__':
    test()
