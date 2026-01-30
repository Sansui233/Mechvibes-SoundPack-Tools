from __future__ import annotations

import io
import zipfile
from pathlib import Path

from pydub import AudioSegment

from mspt.io_utils import read_json
from mspt.rules import compile_matcher
from mspt.sourcemap import iter_sourcemap_entries


def _is_derived_variant(filename: str) -> tuple[str, str] | None:
    """Return (base_filename, variant) for derived segment names.

    Supports:
    - "X-up.ogg" -> ("X.ogg", "up")
    - "X-down.ogg" -> ("X.ogg", "down")
    """

    p = Path(filename)
    suffix = p.suffix
    stem = p.stem
    if stem.endswith("-up"):
        base = f"{stem[:-3]}{suffix}"
        return base, "up"
    if stem.endswith("-down"):
        base = f"{stem[:-5]}{suffix}"
        return base, "down"
    return None


def _split_pairs(
    pairs: list[tuple[float, float]], *, variant: str
) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for start, end in pairs:
        mid = (start + end) / 2
        if variant == "up":
            out.append((mid, end))
        else:
            out.append((start, mid))
    return out


def _materialize_v2_assets(*, target_dir: Path, config: dict) -> dict[str, bytes]:
    """Generate audio assets needed by a Mechvibes V2 config.

    This reads `sourcemap.json` and slices `audio_file` (typically `sound.ogg`)
    into concrete audio files referenced by the v2 config (including pattern/
    brace-range matches).
    """

    sourcemap_path = target_dir / "sourcemap.json"
    if not sourcemap_path.exists():
        raise FileNotFoundError(
            f"sourcemap.json not found at {sourcemap_path} (run prepare first)"
        )
    sourcemap = read_json(sourcemap_path)

    audio_file = str(sourcemap.get("audio_file", "sound.ogg") or "sound.ogg")
    audio_path = target_dir / audio_file
    if not audio_path.exists():
        raise FileNotFoundError(
            f"Audio file referenced by sourcemap not found: {audio_path}"
        )

    file_to_timings: dict[str, list[tuple[float, float]]] = {}
    for entry in iter_sourcemap_entries(sourcemap):
        if not entry.file:
            continue
        file_to_timings.setdefault(entry.file, []).extend(entry.timing)

    available_files = list(file_to_timings.keys())
    if not available_files:
        raise ValueError("No files found in sourcemap.json")

    required_patterns: set[str] = set()
    for key in ("sound", "soundup"):
        value = config.get(key)
        if isinstance(value, str) and value:
            required_patterns.add(value)

    defines = config.get("defines", {})
    if isinstance(defines, dict):
        for value in defines.values():
            if isinstance(value, str) and value:
                required_patterns.add(value)

    needed_files: set[str] = set()
    for pattern in sorted(required_patterns):
        derived = _is_derived_variant(pattern)
        if derived is not None:
            base_pattern, variant = derived
            if base_pattern in file_to_timings:
                needed_files.add(pattern)
                continue

            matcher = compile_matcher(base_pattern)
            base_matches = [name for name in available_files if matcher(name)]
            if not base_matches:
                if (target_dir / pattern).exists():
                    continue
                raise FileNotFoundError(
                    f"Config references '{pattern}', but it matches no base files in sourcemap.json"
                )
            for base in base_matches:
                stem = Path(base).stem
                ext = Path(base).suffix
                needed_files.add(f"{stem}-{variant}{ext}")
            continue

        if pattern in file_to_timings:
            needed_files.add(pattern)
            continue

        matcher = compile_matcher(pattern)
        matches = [name for name in available_files if matcher(name)]
        if not matches:
            # Allow packs that provide real files in target_dir.
            if (target_dir / pattern).exists():
                continue
            raise FileNotFoundError(
                f"Config references '{pattern}', but it matches no files in sourcemap.json"
            )
        needed_files.update(matches)

    if not needed_files:
        return {}

    combined = AudioSegment.from_file(audio_path)
    out: dict[str, bytes] = {}
    for filename in sorted(needed_files):
        timings = file_to_timings.get(filename)
        if not timings:
            derived = _is_derived_variant(filename)
            if derived is None:
                continue
            base, variant = derived
            base_timings = file_to_timings.get(base)
            if not base_timings:
                continue
            timings = _split_pairs(base_timings, variant=variant)

        segment = AudioSegment.empty()
        for start, end in timings:
            segment += combined[int(round(start)) : int(round(end))]

        buf = io.BytesIO()
        suffix = Path(filename).suffix.lower()
        if suffix == ".wav":
            segment.export(buf, format="wav")
        else:
            # Default to ogg to avoid ogg->wav roundtrip without quality gain.
            segment.export(buf, format="ogg", codec="libvorbis", bitrate="192k")
        out[filename] = buf.getvalue()
    return out


def pack_target(target_dir: Path, config_variant: str | None = None) -> Path:
    if not target_dir.exists():
        raise FileNotFoundError(f"target dir not found at {target_dir}")

    suffix = f".{config_variant}" if config_variant else ""
    zip_path = target_dir.parent / f"{target_dir.name}{suffix}.zip"

    variant_path: Path | None = None
    if config_variant:
        variant_path = target_dir / f"config.{config_variant}.json"
        if not variant_path.exists():
            raise FileNotFoundError(
                f"config variant not found: {variant_path} (run build with --schema {config_variant}|all)"
            )

    v2_assets: dict[str, bytes] = {}
    if config_variant == "v2" and variant_path is not None:
        config = read_json(variant_path)
        v2_assets = _materialize_v2_assets(target_dir=target_dir, config=config)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(target_dir.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.name == "sourcemap.json":
                continue
            if file_path.name == "config.json":
                continue
            if config_variant == "v2" and file_path.name == "sound.ogg":
                # V2 is file-based; sound.ogg is only an intermediate slicing source.
                continue
            if file_path.name.startswith("config.") and file_path.name.endswith(
                ".json"
            ):
                continue
            if config_variant == "v2" and file_path.name in v2_assets:
                # Prefer the materialized version from sourcemap.
                continue
            arcname = (
                f"{target_dir.name}/{file_path.relative_to(target_dir).as_posix()}"
            )
            archive.write(file_path, arcname=arcname)

        for filename, data in sorted(v2_assets.items()):
            archive.writestr(f"{target_dir.name}/{filename}", data)

        if variant_path is not None:
            archive.write(variant_path, arcname=f"{target_dir.name}/config.json")
    return zip_path
