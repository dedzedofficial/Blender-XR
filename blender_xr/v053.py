# SPDX-License-Identifier: GPL-3.0-or-later
"""v0.5.3 compatibility routing.

Existing runtime/mesh call sites keep their public API, while the actual shared
selection and transform implementations live in purpose-based modules.
"""
from . import selection, transforms


def patch(runtime_module, mesh_module):
    if getattr(runtime_module, '_v053_patched', False):
        return
    runtime_module.matrix_changed = transforms.matrix_changed
    runtime_module.uniform_scaled = transforms.uniform_scaled
    mesh_module.selection_mode = selection.mode
    mesh_module.set_selection_mode = selection.set_mode
    runtime_module._v053_patched = True
