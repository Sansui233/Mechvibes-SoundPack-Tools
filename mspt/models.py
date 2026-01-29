from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SourceEntry:
    name: str
    file: str
    timing: list[tuple[float, float]]
