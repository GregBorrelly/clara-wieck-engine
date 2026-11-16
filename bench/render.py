"""Engrave MusicXML as A4 pages (like a published PDF) and rasterize them at 300 dpi."""
from __future__ import annotations

import cairosvg
import verovio

A4_W_PX = 2480  # 300 dpi


def engrave(musicxml: str, out_prefix: str, scale: int = 100) -> list[str]:
    tk = verovio.toolkit()
    tk.setOptions({
        "pageWidth": 2100, "pageHeight": 2970, "pageMarginLeft": 100, "pageMarginRight": 100,
        "pageMarginTop": 100, "pageMarginBottom": 100, "scale": scale, "adjustPageHeight": False,
        "breaks": "auto", "header": "auto", "footer": "none", "svgViewBox": True,
    })
    if not tk.loadData(musicxml):
        raise ValueError("verovio could not load the MusicXML")
    paths = []
    for p in range(1, tk.getPageCount() + 1):
        svg = tk.renderToSVG(p)
        path = f"{out_prefix}-p{p}.png"
        cairosvg.svg2png(bytestring=svg.encode(), write_to=path, output_width=A4_W_PX, background_color="white")
        paths.append(path)
    return paths
