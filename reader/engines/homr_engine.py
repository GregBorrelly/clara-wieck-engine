"""homr (AGPL-3.0, github.com/liebharc/homr): staff detection plus a transformer that reads each staff."""
from __future__ import annotations

import io
import os
import time
from contextlib import redirect_stderr, redirect_stdout

from .base import Engine, PageResult


class HomrEngine(Engine):
    name = "homr"

    def __init__(self) -> None:
        self._ready = False

    def available(self) -> bool:
        try:
            import homr  # noqa: F401
        except ImportError:
            return False
        return True

    def _prepare(self) -> None:
        if self._ready:
            return
        from homr.main import download_weights

        download_weights(segnet_use_gpu=False, transformer_use_gpu=False, coreml_encoder=False)
        self._ready = True

    def read_page(self, image_path: str) -> PageResult:
        from homr.main import ProcessingConfig, process_image
        from homr.music_xml_generator import XmlGeneratorArguments

        self._prepare()
        config = ProcessingConfig(
            enable_debug=False, enable_cache=False, write_staff_positions=True, read_staff_positions=False,
            selected_staff=-1, transformer_use_gpu=False, segnet_use_gpu=False, coreml_encoder=False,
            title_detection=False,
        )
        log = io.StringIO()
        start = time.perf_counter()
        with redirect_stderr(log), redirect_stdout(log):
            xml_path = process_image(image_path, config, XmlGeneratorArguments())
        seconds = time.perf_counter() - start
        with open(xml_path, encoding="utf-8") as f:
            xml = f.read()
        systems = read_positions(os.path.splitext(image_path)[0] + ".txt")
        for leftover in (xml_path, os.path.splitext(image_path)[0] + "_teaser.png", os.path.splitext(image_path)[0] + ".txt"):
            if os.path.exists(leftover):
                os.remove(leftover)
        notes = [line.strip() for line in log.getvalue().splitlines()
                 if "connected staffs" in line or "Systems after" in line or "Found" in line and "staffs" in line]
        return PageResult(musicxml=xml, seconds=seconds, engine=self.name, notes=notes, systems=systems)


def read_positions(path: str) -> list[dict]:
    """homr's staff position file: one line per system, "class cx cy w h", all as fractions of the page."""
    out = []
    if not os.path.exists(path):
        return out
    for line in open(path):
        parts = line.split()
        if len(parts) != 5:
            continue
        _, cx, cy, w, h = map(float, parts)
        out.append({"left": round(cx - w / 2, 4), "top": round(cy - h / 2, 4), "right": round(cx + w / 2, 4), "bottom": round(cy + h / 2, 4)})
    out.sort(key=lambda b: b["top"])
    return out
