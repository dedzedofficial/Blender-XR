# SPDX-License-Identifier: GPL-3.0-or-later
"""Single source of truth for XR Mesh's Python/UI version string."""

VERSION = (0, 5, 6)
VERSION_TEXT = '.'.join(str(part) for part in VERSION)
DISPLAY_VERSION = 'V' + VERSION_TEXT
