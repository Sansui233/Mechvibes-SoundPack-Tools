from __future__ import annotations

import warnings
from pathlib import Path
from typing import Iterable

from pydub import AudioSegment

from mspt.io_utils import write_json
from mspt.models import SourceEntry
from mspt.paths import iter_audio_files

warnings.filterwarnings("ignore", category=SyntaxWarning, module=r"pydub\.utils")


def concat_audio(files: Iterable[Path]) -> tuple[AudioSegment, list[SourceEntry]]:
    combined = AudioSegment.empty()
    entries: list[SourceEntry] = []
    current_ms = 0.0
    for file_path in files:
        segment = AudioSegment.from_file(file_path)
        start = current_ms
        end = current_ms + len(segment)
        entries.append(
            SourceEntry(
                name=file_path.stem,
                file=file_path.name,
                timing=[(float(start), float(end))],
            )
        )
        combined += segment
        current_ms = end
    return combined, entries


def generate_sourcemap(source_dir: Path, target_dir: Path) -> Path:
    audio_files = iter_audio_files(source_dir)
    if not audio_files:
        raise ValueError(f"No audio files found in {source_dir}")

    target_dir.mkdir(parents=True, exist_ok=True)
    combined, entries = concat_audio(audio_files)
    ogg_path = target_dir / "sound.ogg"
    combined.export(ogg_path, format="ogg", codec="libvorbis", bitrate="192k")

    sourcemap = {
        "audio_file": ogg_path.name,
        "source_dir": str(source_dir),
        "files": [
            {
                "name": entry.name,
                "file": entry.file,
                "timing": [[t[0], t[1]] for t in entry.timing],
            }
            for entry in entries
        ],
    }
    sourcemap_path = target_dir / "sourcemap.json"
    write_json(sourcemap_path, sourcemap)
    return sourcemap_path
