from __future__ import annotations

from pathlib import Path
from typing import Iterable

from mspt.models import SourceEntry


def iter_sourcemap_entries(sourcemap: dict) -> list[SourceEntry]:
    """Normalize sourcemap into a flat list of SourceEntry.

    Supports both:
    - legacy format: {"files": [{"name","file","timing": [[start,end], ...]}]}
    - docs format: {"sounds": [{"name": str, "files": [{"filename.wav": [start,end]}, ...]}]}

    Output entries always use:
    - entry.name: virtual sound name
    - entry.file: virtual segment filename (e.g. "1.wav")
    - entry.timing: list of (startMs,endMs) pairs
    """

    if isinstance(sourcemap.get("sounds"), list):
        entries: list[SourceEntry] = []
        for sound in sourcemap.get("sounds", []):
            name = str(sound.get("name", ""))
            for file_map in sound.get("files", []) or []:
                if not isinstance(file_map, dict):
                    continue
                for filename, timing in file_map.items():
                    if not filename:
                        continue
                    if not isinstance(timing, (list, tuple)) or len(timing) != 2:
                        continue
                    start, end = float(timing[0]), float(timing[1])
                    entries.append(
                        SourceEntry(
                            name=name, file=str(filename), timing=[(start, end)]
                        )
                    )
        return entries

    files = sourcemap.get("files", [])
    entries = [
        SourceEntry(
            name=item.get("name", ""),
            file=item.get("file", item.get("name", "")),
            timing=[tuple(pair) for pair in item.get("timing", [])],
        )
        for item in files
    ]
    return entries


def list_sourcemap_filenames(sourcemap: dict) -> list[str]:
    """Return all concrete filenames referenced by sourcemap (deduped, stable)."""
    seen: dict[str, None] = {}
    for entry in iter_sourcemap_entries(sourcemap):
        if entry.file:
            seen.setdefault(entry.file, None)
    return list(seen.keys())


def resolve_source_dir(sourcemap: dict, *, target_dir: Path) -> Path:
    """Resolve sourcemap.source_dir to an absolute Path.

    - If sourcemap contains an absolute path, return it.
    - If it is relative, interpret it as relative to repo CWD (current behavior).
      (We don't assume target_dir relationship because prior sourcemaps stored
      paths like "sounds\\bubble".)
    """

    raw = sourcemap.get("source_dir")
    if not raw:
        return target_dir
    p = Path(str(raw))
    return p


def is_single_audio_method(sourcemap: dict) -> bool:
    """True if the pack is fundamentally based on a single audio file + timestamps."""
    audio_file = str(sourcemap.get("audio_file", "") or "")
    return bool(audio_file)
