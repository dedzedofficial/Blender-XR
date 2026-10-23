#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Rasterize bundled Blender UI SVG artwork into transparent GPU-ready PNGs.

The SVGs remain the source of truth. 128px textures improve sampling in
world-space XR menus while remaining small enough for the icon cache.

Run from the repository root after installing CairoSVG:
    python -m pip install cairosvg
    python tools/build_icon_textures.py
"""
from pathlib import Path
import cairosvg

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blender_xr" / "icons_src"
OUTPUT = ROOT / "blender_xr" / "icons"
SIZE = 128


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    sources = sorted(SOURCE.glob("*.svg"))
    if not sources:
        raise SystemExit(f"No SVG icon sources found in {SOURCE}")
    for source in sources:
        destination = OUTPUT / (source.stem + ".png")
        cairosvg.svg2png(
            url=str(source),
            write_to=str(destination),
            output_width=SIZE,
            output_height=SIZE,
        )
        print(f"{source.name} -> {destination.relative_to(ROOT)} ({SIZE}x{SIZE})")


if __name__ == "__main__":
    main()
