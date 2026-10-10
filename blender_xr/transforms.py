# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared object transform helpers used by gizmos and future direct-hand tools."""


def matrix_changed(first, second, epsilon=1e-8):
    return any(abs(first[row][column]-second[row][column]) > epsilon
               for row in range(4) for column in range(4))


def uniform_scaled(matrix, factor):
    result = matrix.copy()
    for row in range(3):
        for column in range(3):
            result[row][column] = matrix[row][column] * factor
    result.translation = matrix.translation
    return result


def object_history_entry(obj, before):
    after = obj.matrix_world.copy()
    if not matrix_changed(before, after):
        return None
    return ('OBJECT', obj.name, None, before, after)


def ensure_object_transformable(obj):
    if not obj or obj.type != 'MESH':
        raise ValueError('Select a mesh object first')
    if obj.library or obj.parent or obj.constraints:
        raise ValueError('Object transforms require a local unparented object without constraints')
    return obj


def ensure_idle(runtime):
    if runtime.transaction or runtime.grab or runtime.air_grab or runtime.axis_move:
        raise ValueError('Finish or cancel the current operation first')
