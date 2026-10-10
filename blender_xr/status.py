# SPDX-License-Identifier: GPL-3.0-or-later
"""Consistent short status messages shared by desktop and XR UI."""


def set_status(target, message):
    text = str(message).strip()
    if hasattr(target, 'status'):
        target.status = text
    settings = getattr(target, 'settings', None)
    if settings is not None and hasattr(settings, 'status'):
        settings.status = text
    return text


def selected(kind):
    return kind.upper() + ' SELECTED'


def material_assigned(material_name, face_count):
    return f'{face_count} FACE' + ('' if face_count == 1 else 'S') + ' → ' + material_name


def operation(label):
    return str(label).upper() + ' / UNDO TO RESTORE'
