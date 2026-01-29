from __future__ import annotations

from pathlib import Path

AUDIO_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".ogg",
    ".flac",
    ".m4a",
    ".aac",
    ".aiff",
    ".aif",
    ".opus",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def iter_audio_files(source_dir: Path) -> list[Path]:
    files = [
        p
        for p in source_dir.iterdir()
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
    ]
    return sorted(files, key=lambda p: p.name.lower())


def find_license_file(source_dir: Path) -> Path | None:
    for item in sorted(source_dir.iterdir(), key=lambda p: p.name.lower()):
        if item.is_file() and item.name.lower().startswith("license"):
            return item
    return None


def find_icon_file(source_dir: Path) -> Path | None:
    for item in sorted(source_dir.iterdir(), key=lambda p: p.name.lower()):
        if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS:
            return item
    return None


def resolve_target_dir(input_dir: Path) -> Path:
    return Path("target") / input_dir.name


def resolve_sourcemap_path(input_path: Path) -> Path:
    if input_path.is_dir():
        return input_path / "sourcemap.json"
    return input_path


def resolve_pack_dir(input_path: Path) -> Path:
    if input_path.is_file() and input_path.name == "sourcemap.json":
        return input_path.parent
    if input_path.is_dir():
        if (input_path / "config.json").exists():
            return input_path
        return resolve_target_dir(input_path)
    raise FileNotFoundError(f"pack source not found at {input_path}")
