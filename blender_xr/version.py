# SPDX-License-Identifier: GPL-3.0-or-later
"""Single source of truth for Mesh XR's Python/UI version string."""

VERSION = (0, 6, 5)
VERSION_TEXT = '.'.join(str(part) for part in VERSION)
DISPLAY_VERSION = 'V' + VERSION_TEXT
