from __future__ import annotations

import zipfile
from pathlib import Path


def pack_target(target_dir: Path) -> Path:
    if not target_dir.exists():
        raise FileNotFoundError(f"target dir not found at {target_dir}")
    zip_path = target_dir.parent / f"{target_dir.name}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(target_dir.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.name == "sourcemap.json":
                continue
            arcname = (
                f"{target_dir.name}/{file_path.relative_to(target_dir).as_posix()}"
            )
            archive.write(file_path, arcname=arcname)
    return zip_path
