from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, cast, get_args

from mspt.keycodes import keyname_to_keycode
from mspt.rules import (
    compile_matcher,
    load_key_names,
    resolve_key_selectors,
    to_list,
)
from mspt.schema.mechvibes_v1 import MechvibesV1Schema
from mspt.schema.mechvibes_v2 import MechvibesV2Schema
from mspt.schema.mvdx import DefinitionKey, KeyName, MVDXSchema
from mspt.sourcemap import iter_sourcemap_entries


@dataclass(frozen=True)
class KeyTimings:
    down: tuple[float, float] | None
    up: tuple[float, float] | None


@dataclass(frozen=True)
class MechvibesV2Inputs:
    sound: str
    soundup: str
    keydown_defines: dict[KeyName, str]
    keyup_defines: dict[KeyName, str]
    # True when this pack should emit key-up defines (either because --split
    # was used, or because at least one rule uses *_UP / _UP selectors).
    has_keyup_rules: bool


def _with_suffix(filename_or_pattern: str, suffix: str) -> str:
    """Insert `suffix` before extension, preserving patterns.

    Example: "1.ogg" + "-up" -> "1-up.ogg"
    """

    if not filename_or_pattern:
        return filename_or_pattern
    if filename_or_pattern.endswith(f"{suffix}.ogg") or filename_or_pattern.endswith(
        f"{suffix}.wav"
    ):
        return filename_or_pattern
    dot = filename_or_pattern.rfind(".")
    if dot == -1:
        return f"{filename_or_pattern}{suffix}"
    return f"{filename_or_pattern[:dot]}{suffix}{filename_or_pattern[dot:]}"


def _timing_pair_to_clip(pair: tuple[float, float]) -> list[int]:
    start, end = pair
    start_i = int(round(start))
    length_i = int(round(end - start))
    if length_i < 0:
        raise ValueError(f"Invalid timing pair: start={start} end={end}")
    return [start_i, length_i]


def mvdx_definitions_to_keytimings(
    definitions: dict[KeyName, DefinitionKey] | dict[str, dict],
) -> dict[KeyName, KeyTimings]:
    out: dict[KeyName, KeyTimings] = {}
    valid_keys = set(get_args(KeyName))
    for key, value in definitions.items():
        key_name = cast(KeyName, key) if key in valid_keys else None
        if key_name is None:
            continue

        # accept either typed model objects or raw dicts
        if isinstance(value, dict):
            timing = value.get("timing", [])
        else:
            timing = value.timing

        pairs: list[tuple[float, float]] = []
        for raw_pair in timing:
            if len(raw_pair) != 2:
                raise ValueError(
                    f"Invalid timing pair for key '{key_name}': expected 2 items, got {len(raw_pair)}"
                )
            pairs.append((float(raw_pair[0]), float(raw_pair[1])))
        down = pairs[0] if len(pairs) >= 1 else None
        up = pairs[1] if len(pairs) >= 2 else None
        out[key_name] = KeyTimings(down=down, up=up)
    return out


def to_mechvibes_v1(
    *,
    mvdx: MVDXSchema,
    includes_numpad: bool = True,
    dx_compatible: bool = False,
) -> MechvibesV1Schema:
    keytimings = mvdx_definitions_to_keytimings(mvdx.definitions)

    defines: dict[str, list[int] | str] = {}
    for key, timing in keytimings.items():
        if timing.down is None:
            continue
        # V1 has no native key-up channel, but we can represent a combined
        # keydown+keyup sound by emitting a single clip that spans both.
        if timing.up is not None:
            down_start, _down_end = timing.down
            _up_start, up_end = timing.up
            combined = (float(down_start), float(up_end))
            keycode = str(keyname_to_keycode(key))
            defines[keycode] = _timing_pair_to_clip(combined)
            continue
        keycode = str(keyname_to_keycode(key))
        defines[keycode] = _timing_pair_to_clip(timing.down)

    return MechvibesV1Schema(
        id=mvdx.id,
        name=mvdx.name,
        author=mvdx.author,
        icon=mvdx.icon,
        tags=list(mvdx.tags),
        key_define_type="single",
        includes_numpad=includes_numpad,
        sound=mvdx.audio_file,
        defines=defines,
        version="1" if dx_compatible else 1,
    )


def _all_keynames(keys: Iterable[KeyName] | None) -> list[KeyName]:
    if keys is None:
        return []
    return list(keys)


def to_mechvibes_v2(
    *,
    id: str,
    name: str,
    sound: str,
    soundup: str,
    keydown_defines: dict[KeyName, str],
    keyup_defines: dict[KeyName, str],
    fill_missing_up: bool = True,
    all_keys: Iterable[KeyName] | None = None,
    author: str | None = None,
    icon: str | None = None,
    tags: list[str] | None = None,
    dx_compatible: bool = False,
) -> MechvibesV2Schema:
    defines: dict[str, str] = {}

    for key, filename in keydown_defines.items():
        defines[str(keyname_to_keycode(key))] = filename

    for key, filename in keyup_defines.items():
        defines[f"{keyname_to_keycode(key)}-up"] = filename

    if fill_missing_up:
        for key in _all_keynames(all_keys):
            up_key = f"{keyname_to_keycode(key)}-up"
            if up_key not in defines:
                defines[up_key] = soundup

    return MechvibesV2Schema(
        id=id,
        name=name,
        author=author,
        icon=icon,
        tags=tags or [],
        key_define_type="multi",
        sound=sound,
        soundup=soundup,
        defines=defines,
        version="2" if dx_compatible else 2,
    )


def build_mechvibes_v2_inputs(
    *,
    sourcemap: dict,
    rule: dict | None,
    split: bool,
) -> MechvibesV2Inputs:
    """Convert sourcemap+rule into inputs for Mechvibes V2 (multi-file) config.

    This is file-definition based ("defines" values are filenames / patterns),
    matching Mechvibes wiki v2 behavior.

    `_UP` in rule selectors targets key-up definitions.
    """

    key_names = load_key_names()
    keys: list[KeyName] = [k for k in key_names]  # type: ignore[assignment]
    key_name_set = {k.lower() for k in keys}

    entries = [
        {"name": entry.name, "file": entry.file}
        for entry in iter_sourcemap_entries(sourcemap)
    ]
    if not entries:
        raise ValueError("No entries found in sourcemap.json")

    rule_map = None
    if rule:
        if isinstance(rule.get("map"), dict):
            rule_map = rule["map"]
        elif isinstance(rule, dict):
            rule_map = rule

    keydown_defines: dict[KeyName, str] = {}
    keyup_defines: dict[KeyName, str] = {}
    used_indices: set[int] = set()

    fallback_down: str | None = None
    fallback_up: str | None = None
    fallback_down_from_rule = False
    enable_keyup = False

    if rule_map and isinstance(rule_map, dict):
        for pattern, selectors in rule_map.items():
            if pattern == "fallback" and isinstance(selectors, str):
                # legacy alias support
                fallback_down = fallback_down or selectors
                continue

            selector_list = to_list(selectors)
            has_fallback_down = "*" in selector_list
            has_fallback_up = "*_UP" in selector_list
            if has_fallback_down:
                selector_list = [item for item in selector_list if item != "*"]
            if has_fallback_up:
                selector_list = [item for item in selector_list if item != "*_UP"]

            # Group selectors by channel
            down_selectors: list[str] = []
            up_selectors: list[str] = []
            for sel in selector_list:
                if isinstance(sel, str) and sel.endswith("_UP"):
                    up_selectors.append(sel[: -len("_UP")])
                else:
                    down_selectors.append(sel)

            matcher = compile_matcher(pattern)
            matched_any = False
            for idx, entry in enumerate(entries):
                if idx in used_indices:
                    continue
                if matcher(entry["file"]):
                    matched_any = True
                    used_indices.add(idx)

            if matched_any:
                if has_fallback_down and fallback_down is None:
                    fallback_down = pattern
                    fallback_down_from_rule = True
                if has_fallback_up and fallback_up is None:
                    fallback_up = pattern

                # Only treat this pack as having key-up behavior when at least
                # one key-up selector successfully matches an existing file.
                if up_selectors or has_fallback_up:
                    enable_keyup = True

                if down_selectors:
                    target_keys = resolve_key_selectors(down_selectors, key_names)
                    for k in target_keys:
                        if k not in keydown_defines:
                            keydown_defines[k] = pattern  # type: ignore[index]
                if up_selectors:
                    target_keys = resolve_key_selectors(up_selectors, key_names)
                    for k in target_keys:
                        if k not in keyup_defines:
                            keyup_defines[k] = pattern  # type: ignore[index]

    # Fallback sounds if not explicitly provided by rule
    if fallback_down is None:
        fallback_down = str(entries[0]["file"])
    if fallback_up is None:
        fallback_up = fallback_down

    fallback_down = cast(str, fallback_down)
    fallback_up = cast(str, fallback_up)

    # When split is requested, we always generate key-up definitions.
    if split:
        enable_keyup = True

    # Fill keydown definitions:
    # 1) Direct match by entry name (e.g. entry name "enter" -> key "Enter")
    # 2) Reserve key-named files (e.g. enter.wav) from automatic distribution
    # 3) Fill remaining keys:
    #    - if rule has '*' fallback: use that fallback file
    #    - else: cycle through the remaining (non-reserved, non-rule-matched) files
    for idx, entry in enumerate(entries):
        name = entry.get("name", "")
        if not name:
            continue
        for k in keys:
            if k in keydown_defines:
                continue
            if k.lower() == name.lower():
                keydown_defines[k] = entry["file"]
                break

    # Reserve any key-named files from auto distribution unless the user
    # explicitly assigns them via rule patterns.
    for idx, entry in enumerate(entries):
        name = str(entry.get("name", "") or "")
        if name and name.lower() in key_name_set:
            used_indices.add(idx)

    remaining_entries = [
        entry for idx, entry in enumerate(entries) if idx not in used_indices
    ]
    cycle_files = [str(entry["file"]) for entry in remaining_entries] or [fallback_down]

    for i, k in enumerate(keys):
        if k in keydown_defines:
            continue
        # If the user provided a fallback rule ('*'), keep behavior stable: use
        # that fallback file for all unspecified keys.
        if fallback_down_from_rule:
            keydown_defines[k] = fallback_down
        else:
            keydown_defines[k] = cycle_files[i % len(cycle_files)]

    # In split mode, derive key-up filenames from each key's down filename
    # unless the rule explicitly assigned an up mapping.
    if split:
        for k in keys:
            if k in keyup_defines:
                continue
            down = keydown_defines.get(k)
            if down:
                keyup_defines[k] = _with_suffix(down, "-up")

        # Default soundup should follow sound unless the rule provided an
        # explicit key-up fallback.
        if fallback_up == fallback_down:
            fallback_up = _with_suffix(fallback_down, "-up")

    return MechvibesV2Inputs(
        sound=fallback_down,
        soundup=fallback_up,
        keydown_defines=keydown_defines,
        keyup_defines=keyup_defines,
        has_keyup_rules=enable_keyup,
    )
