# SPDX-License-Identifier: GPL-3.0-or-later
"""Save real Blender projects while keeping VR-local undo snapshots in memory."""
from contextlib import contextmanager
from pathlib import Path
import time
import bpy


def choose_path(current, requested='', directory=None):
    if current:
        return Path(current).resolve()
    if requested.strip():
        target = Path(requested).expanduser()
        if not target.is_absolute():
            raise ValueError('Choose an absolute save path for an unsaved project')
        if target.suffix.lower() != '.blend':
            target = target.with_suffix('.blend')
        if target.exists():
            raise ValueError('Save path already exists; open that project or choose a new filename')
        return target
    folder = Path(directory) if directory is not None else Path.home() / 'Documents' / 'BlenderXR'
    stem = 'BlenderXR-' + time.strftime('%Y%m%d-%H%M%S')
    target = folder / (stem + '.blend')
    count = 1
    while target.exists():
        target = folder / (stem + '-' + str(count) + '.blend')
        count += 1
    return target


@contextmanager
def without_snapshots(history):
    """Zero-user mesh snapshots stay in memory but are excluded from saving."""
    flags = []
    seen = set()
    try:
        for entry in (history.undo + history.redo) if history else ():
            ids = entry[3:5] if entry[0] == 'MESH' else (entry[3],) if entry[0] == 'CREATE' else ()
            for item in ids:
                if item is not None and item.as_pointer() not in seen:
                    seen.add(item.as_pointer())
                    flags.append((item, item.use_fake_user))
                    item.use_fake_user = False
        yield
    finally:
        for item, value in flags:
            item.use_fake_user = value


def save(context, history=None):
    settings = context.scene.blender_xr
    target = choose_path(bpy.data.filepath, settings.save_path)
    previous = settings.save_path
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Flush committed edit-cage changes before writing the project.
        for obj in context.objects_in_mode:
            if obj.type == 'MESH':
                obj.update_from_editmode()
        settings.save_path = str(target)
        with without_snapshots(history):
            result = bpy.ops.wm.save_as_mainfile(filepath=str(target), check_existing=False)
        if 'FINISHED' not in result:
            raise ValueError('Blender could not save the project')
    except (OSError, RuntimeError, ValueError) as exc:
        settings.save_path = previous
        raise ValueError('Save failed: ' + str(exc)) from exc
    return target
