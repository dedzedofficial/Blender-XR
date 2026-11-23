# SPDX-License-Identifier: GPL-3.0-or-later
"""Invalidate session-only authoring approvals after an unsafe input boundary.

A native Blender edit is committed only by its explicit menu command. The
editor keeps a small set of read-only pending approvals (shape-key creation,
renaming and animation keyframe deletion) until that command. Never carry
those approvals across OpenXR tracking loss, session loss, gesture conflict
or a failed native rollback: a reconnect must require a NEW deliberate
selection and confirmation.

This file does not modify Blender datablocks, edit history or live gesture
rollback state; the existing input-ownership canceller owns those mutations.
"""


# These are only the transient authoring screens. They are *not* live mesh,
# rig or paint gestures: clearing them must not bypass a pending rollback.
_SAFE_PAGE_AFTER_LOSS = {
    'XR_SHAPE_CREATE_CONFIRM_090': 'XR_SHAPE_MANAGE_090',
    'XR_SHAPE_RENAME_090': 'XR_SHAPE_MANAGE_090',
    'XR_KEY_DELETE_CONFIRM_090': 'XR_INTERP_PICK_090',
    'XR_INTERP_STYLE_090': 'XR_INTERP_PICK_090',
    'XR_WELD_CONFIRM_090': 'XR_WELD_PREVIEW_090',
    'XR_NUMERIC_MOVE_090': 'XR_SNAP_AXIS_090',
    'XR_NUMERIC_MOVE_DIGITS_090': 'XR_SNAP_AXIS_090',
}


def expire_pending_approvals(session):
    """Drop approval tokens and take the wrist out of confirmation screens.

    Safe to call repeatedly, including after an earlier failed cancel_work().
    The menu still exists and remains usable after an intentional controller
    neutral rearm. The lost-input frame never invokes a command or Undo.
    """
    if session is None:
        return False
    fields = (
        '_xr_shape_create_pending',
        '_xr_shape_rename_state',
        '_xr_key_delete_pending',
        '_xr_interp_target',
        '_xr_interp_source',
        '_xr_weld_pending',
        '_xr_numeric_move_state',
    )
    had_tokens = any(getattr(session, name, None) is not None for name in fields)
    source = getattr(session, '_xr_interp_source', None)
    for field in fields:
        if hasattr(session, field):
            setattr(session, field, None)

    menu = getattr(session, 'menu', None)
    if menu is None:
        return had_tokens
    old_page = getattr(menu, 'page', None)
    next_page = _SAFE_PAGE_AFTER_LOSS.get(old_page)
    if old_page in {'XR_KEY_DELETE_CONFIRM_090', 'XR_INTERP_STYLE_090'}:
        # A shape-key curve cannot be selected from the nine-channel picker;
        # return to its owner, which has a fresh read-only current-key check.
        next_page = ('XR_SHAPE_KEYFRAMES_090'
                     if source == 'SHAPE' else 'XR_INTERP_PICK_090')
    if next_page is not None:
        menu.page = next_page
    if hasattr(menu, 'tooltip_action'):
        menu.tooltip_action = None
    return had_tokens or (next_page is not None)


def block_unsafe_commands(session, action):
    """Block any mutation while an earlier native-data restore was refused.

    STOP remains available so the artist can exit XR and inspect Blender.
    The two existing input diagnostics remain read-only; SAVE, Undo/Redo,
    mode switching and destructive confirmation are never allowed here.
    """
    if not getattr(session, '_xr_rollback_blocked', False):
        return
    if action in {'STOP', 'FOCUS_STATS', 'FOCUS_INPUT'}:
        return
    raise ValueError(
        'XR rollback blocked; review the Blender scene and restart XR')
