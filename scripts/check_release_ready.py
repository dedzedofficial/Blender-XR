"""Prevent a development package being published as a stable release."""
from pathlib import Path
import runpy


def check_release_ready(root):
    version = runpy.run_path(str(root / "blender_xr" / "version.py"))
    if version.get("RELEASE_CHANNEL") != "stable":
        raise ValueError("Development build: complete the documented platform/headset acceptance before stable publication")


if __name__ == "__main__":
    try:
        check_release_ready(Path(__file__).resolve().parents[1])
    except ValueError as error:
        raise SystemExit(str(error))
