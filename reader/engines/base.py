"""What every reading engine provides: one page image in, MusicXML out."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PageResult:
    musicxml: str
    seconds: float
    engine: str
    notes: list[str] = field(default_factory=list)  # anything the engine reported that a person should know
    systems: list[dict] = field(default_factory=list)  # where each system is, as fractions of the page: left/top/right/bottom


class Engine:
    name = "base"

    def available(self) -> bool:
        return True

    def read_page(self, image_path: str) -> PageResult:  # pragma: no cover - interface
        raise NotImplementedError
