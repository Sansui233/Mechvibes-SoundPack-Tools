from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import cast

from mspt.converters import build_mechvibes_v2_inputs, to_mechvibes_v1, to_mechvibes_v2
from mspt.io_utils import deep_merge, read_json, write_json
from mspt.paths import find_icon_file, find_license_file
from mspt.rules import build_definitions, load_rule
from mspt.schema.mechvibes_v2 import MechvibesV2Schema
from mspt.schema.mvdx import DefinitionKey, KeyName, MVDXSchema


def parse_schema_selector(selector: str) -> set[str]:
    """Parse a schema selector string.

    - "v1|v2" selects both
    - "all" is a special value meaning "v1|v2|mvdx"
    """

    raw = (selector or "").strip().lower()
    if not raw:
        raise ValueError("schema selector is empty")
    if raw == "all":
        return {"v1", "v2", "mvdx"}
    parts = [p.strip() for p in raw.split("|") if p.strip()]
    allowed = {"v1", "v2", "mvdx"}
    unknown = [p for p in parts if p not in allowed]
    if unknown:
        raise ValueError(
            "Invalid --schema value(s): "
            + ", ".join(sorted(set(unknown)))
            + ". Use v1|v2|mvdx or all."
        )
    return set(parts)


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


def to_definition_keys(definitions: dict[str, dict]) -> dict[KeyName, DefinitionKey]:
    out: dict[KeyName, DefinitionKey] = {}
    for key, value in definitions.items():
        timing = value.get("timing", [])
        pairs: list[tuple[float, float]] = []
        for pair in timing:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError(f"Invalid timing pair for key '{key}': {pair}")
            pairs.append((float(pair[0]), float(pair[1])))
        out[cast(KeyName, key)] = DefinitionKey(timing=pairs)
    return out


def generate_config(
    sourcemap_path: Path,
    target_dir: Path,
    split: bool,
    rule_path: Path | None,
    schema: str = "v1|v2",
    dx_compatible: bool = False,
) -> dict[str, Path]:
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
    definitions_typed = to_definition_keys(definitions)

    raw_name = target_dir.name
    mvdx_model_base = MVDXSchema(
        audio_file=str(sourcemap.get("audio_file", "sound.ogg")),
        config_version="2",
        created_at=datetime.now(timezone.utc).isoformat(),
        id=to_id(raw_name),
        name=to_title(raw_name),
        icon=icon_name,
        definitions=definitions_typed,
    )

    # MVDX optionally supports 2 timing pairs per key, which we currently use as
    # a simple keydown/keyup split when requested.
    mvdx_model = mvdx_model_base
    if split:
        split_defs = split_definitions(definitions, split=True)
        mvdx_model = mvdx_model_base.model_copy(
            update={"definitions": to_definition_keys(split_defs)}
        )

    outputs: dict[str, Path] = {}
    wanted = parse_schema_selector(schema)

    if "mvdx" in wanted:
        config = mvdx_model.model_dump(exclude_none=True)
        common_path = Path("rule") / "common.json"
        if common_path.exists():
            config = deep_merge(config, read_json(common_path))
        else:
            try:
                packaged_common = resources.files("rule") / "common.json"
                if packaged_common.is_file():
                    packaged_data = json.loads(
                        packaged_common.read_text(encoding="utf-8")
                    )
                    config = deep_merge(config, packaged_data)
            except ModuleNotFoundError:
                pass

        config = reorder_config(config)
        mvdx_path = target_dir / "config.mvdx.json"
        write_json(mvdx_path, config)
        outputs["mvdx"] = mvdx_path

    if "v1" in wanted:
        # V1 is single-audio + timestamp-based.
        v1_model = to_mechvibes_v1(mvdx=mvdx_model_base, dx_compatible=dx_compatible)
        v1_path = target_dir / "config.v1.json"
        write_json(v1_path, v1_model.model_dump(exclude_none=True))
        outputs["v1"] = v1_path

    if "v2" in wanted:
        # For Mechvibes V2, definitions are file-based; allow _UP rules and
        # treat --split as requesting key-up behavior (multi only in v2).
        v2_inputs = build_mechvibes_v2_inputs(
            sourcemap=sourcemap, rule=rule, split=split
        )
        v2_model: MechvibesV2Schema = to_mechvibes_v2(
            id=mvdx_model_base.id,
            name=mvdx_model_base.name,
            author=mvdx_model_base.author,
            icon=mvdx_model_base.icon,
            tags=list(mvdx_model_base.tags),
            sound=v2_inputs.sound,
            soundup=v2_inputs.soundup,
            keydown_defines=v2_inputs.keydown_defines,
            keyup_defines=v2_inputs.keyup_defines,
            all_keys=v2_inputs.keydown_defines.keys()
            if v2_inputs.has_keyup_rules
            else None,
            fill_missing_up=v2_inputs.has_keyup_rules,
            dx_compatible=dx_compatible,
        )
        v2_path = target_dir / "config.v2.json"
        write_json(v2_path, v2_model.model_dump(exclude_none=True))
        outputs["v2"] = v2_path

    # Note: we intentionally do not copy source audio files into target.
    # Packing should source audio from sourcemap/source_dir (and generate split
    # outputs at pack-time when needed).

    license_file = find_license_file(source_dir)
    if license_file is not None:
        shutil.copy2(license_file, target_dir / license_file.name)

    return outputs
