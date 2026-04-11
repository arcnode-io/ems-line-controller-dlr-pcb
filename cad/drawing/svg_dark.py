"""Convert a light SVG to dark-mode SVG (white lines on black background).

Usage: python cad/drawing/svg_dark.py input.svg output.svg
"""

import sys
from pathlib import Path


def convert(src: Path, dst: Path) -> None:
    """Invert black↔white colors in an SVG and add black background."""
    svg = src.read_text()
    # Reason: full black↔white inversion. Placeholder avoids double-swap.
    # Handles both XML attributes and CSS properties.
    svg = svg.replace("#ffffff", "#__WHITE__")
    svg = svg.replace("#000000", "#ffffff")
    svg = svg.replace("#__WHITE__", "#000000")
    svg = svg.replace('"black"', '"__BLACK__"')
    svg = svg.replace('"white"', '"black"')
    svg = svg.replace('"__BLACK__"', '"white"')
    # Reason: insert a black background rect after the opening <g> tag.
    # CSS background on <svg> is unreliable across viewers.
    svg = svg.replace(
        'transform="translate(0 0) scale(1 1)">',
        'transform="translate(0 0) scale(1 1)">'
        '\n<rect width="100%" height="100%" fill="black"/>',
        1,
    )
    dst.write_text(svg)


if __name__ == "__main__":
    convert(Path(sys.argv[1]), Path(sys.argv[2]))
