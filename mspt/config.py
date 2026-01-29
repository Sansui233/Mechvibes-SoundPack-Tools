from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import cast

from mspt.io_utils import deep_merge, read_json, write_json
from mspt.paths import find_icon_file, find_license_file
from mspt.rules import build_definitions, load_rule
from mspt.schema.v2 import DefinitionKey, KeyName, V2Schema


def to_id(raw_name: str) -> str:
    normalized = re.sub(r"\s+", "-", raw_name.strip())
    return normalized.lower()


def to_title(raw_name: str) -> str:
    cleaned = re.sub(r"[-_]+", " ", raw_name.strip())
    return " ".join(part.capitalize() for part in cleaned.split())


def reorder_config(data: dict) -> dict:
    schema_order = [
        "audio_file",
        "config_version",
        "created_at",
        "definition_method",
        "author",
        "icon",
        "id",
        "name",
        "options",
        "tags",
        "definitions",
    ]
    order = (
        ["id", "name", "author"]
        + [
            key
            for key in schema_order
            if key not in {"id", "name", "author", "definitions"}
        ]
        + ["definitions"]
    )
    return {key: data[key] for key in order if key in data}


def split_timing_pair(pair: tuple[float, float]) -> list[tuple[float, float]]:
    start, end = pair
    mid = (start + end) / 2
    return [(start, mid), (mid, end)]


def split_definitions(definitions: dict[str, dict], split: bool) -> dict[str, dict]:
    if not split:
        return definitions
    updated: dict[str, dict] = {}
    for key, value in definitions.items():
        timing = value.get("timing", [])
        if len(timing) == 1:
            updated[key] = {"timing": split_timing_pair(tuple(timing[0]))}
        else:
            updated[key] = value
    return updated


def generate_config(
    sourcemap_path: Path,
    target_dir: Path,
    split: bool,
    rule_path: Path | None,
) -> Path:
    sourcemap = read_json(sourcemap_path)
    source_dir = Path(sourcemap.get("source_dir", target_dir))
    rule = load_rule(rule_path)

    icon_file = find_icon_file(source_dir)
    if icon_file is not None:
        shutil.copy2(icon_file, target_dir / icon_file.name)
        icon_name = icon_file.name
    else:
        icon_name = None

    definitions = build_definitions(sourcemap, rule=rule)
    definitions = split_definitions(definitions, split)
    definitions_typed = cast(dict[KeyName, DefinitionKey], definitions)

    raw_name = target_dir.name
    model = V2Schema(
        audio_file=str(sourcemap.get("audio_file", "sound.ogg")),
        config_version=2,
        created_at=datetime.now(timezone.utc).isoformat(),
        id=to_id(raw_name),
        name=to_title(raw_name),
        icon=icon_name,
        definitions=definitions_typed,
    )

    config = model.model_dump(exclude_none=True)
    common_path = Path("rule") / "common.json"
    if common_path.exists():
        config = deep_merge(config, read_json(common_path))
    else:
        try:
            packaged_common = resources.files("rule") / "common.json"
            if packaged_common.is_file():
                packaged_data = json.loads(packaged_common.read_text(encoding="utf-8"))
                config = deep_merge(config, packaged_data)
        except ModuleNotFoundError:
            pass

    config = reorder_config(config)

    config_path = target_dir / "config.json"
    write_json(config_path, config)

    license_file = find_license_file(source_dir)
    if license_file is not None:
        shutil.copy2(license_file, target_dir / license_file.name)

    return config_path
