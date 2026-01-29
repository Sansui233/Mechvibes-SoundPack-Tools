from __future__ import annotations

import random
import re
from fnmatch import fnmatchcase
from pathlib import Path
from typing import get_args

from mspt.io_utils import read_json
from mspt.models import SourceEntry
from mspt.schema.v2 import KeyName


def ensure_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return list(value)


def compile_matcher(pattern: str):
    try:
        regex = re.compile(pattern, re.IGNORECASE)
        return lambda text: regex.search(text) is not None
    except re.error:
        return lambda text: fnmatchcase(text.lower(), pattern.lower())


def load_key_names() -> list[str]:
    return list(get_args(KeyName))


def resolve_key_selectors(selectors: list[str], keys: list[str]) -> list[str]:
    resolved: list[str] = []
    for selector in selectors:
        if selector in keys:
            resolved.append(selector)
            continue
        matcher = compile_matcher(selector)
        matched = [key for key in keys if matcher(key)]
        resolved.extend(matched)
    return list(dict.fromkeys(resolved))


def load_rule(rule_path: Path | None) -> dict | None:
    if rule_path is None:
        return None
    if not rule_path.exists():
        raise FileNotFoundError(f"rule file not found at {rule_path}")
    return read_json(rule_path)


def apply_rule_map(
    entries: list[SourceEntry],
    keys: list[str],
    rule_map: dict,
) -> tuple[dict[str, list[tuple[float, float]]], set[int], SourceEntry | None]:
    buckets: dict[str, list[tuple[float, float]]] = {key: [] for key in keys}
    used_indices: set[int] = set()
    fallback_entry: SourceEntry | None = None

    for pattern, selectors in rule_map.items():
        selector_list = ensure_list(selectors)
        has_fallback = "*" in selector_list
        if has_fallback:
            selector_list = [item for item in selector_list if item != "*"]
        matcher = compile_matcher(pattern)
        target_keys = resolve_key_selectors(selector_list, keys)
        for idx, entry in enumerate(entries):
            if idx in used_indices:
                continue
            if matcher(entry.file):
                used_indices.add(idx)
                if has_fallback and fallback_entry is None:
                    fallback_entry = entry
                if not target_keys:
                    continue
                for key in target_keys:
                    if len(buckets[key]) >= 2:
                        raise ValueError(f"Key '{key}' exceeds timing limit (max 2).")
                    buckets[key].extend(entry.timing)

    return buckets, used_indices, fallback_entry


def assign_direct_matches(
    remaining_entries: list[SourceEntry],
    candidate_keys: list[str],
) -> tuple[dict[str, SourceEntry], list[SourceEntry]]:
    direct_map: dict[str, SourceEntry] = {}
    remaining_after_match: list[SourceEntry] = []
    for entry in remaining_entries:
        matched_key = next(
            (k for k in candidate_keys if k.lower() == entry.name.lower()),
            None,
        )
        if matched_key and matched_key not in direct_map:
            direct_map[matched_key] = entry
        else:
            remaining_after_match.append(entry)
    return direct_map, remaining_after_match


def assign_round_robin(
    remaining_entries: list[SourceEntry],
    candidate_keys: list[str],
    buckets: dict[str, list[tuple[float, float]]],
) -> None:
    available_keys = list(candidate_keys)
    for entry in remaining_entries:
        if not available_keys:
            break
        key = available_keys.pop(0)
        buckets[key].extend(entry.timing[:1])


def fill_empty_with_random(
    keys: list[str],
    buckets: dict[str, list[tuple[float, float]]],
    entries: list[SourceEntry],
    rng: random.Random,
) -> None:
    for key in keys:
        if not buckets[key]:
            pick = rng.choice(entries)
            buckets[key].extend(pick.timing[:1])


def build_definitions(sourcemap: dict, rule: dict | None) -> dict[str, dict]:
    keys = load_key_names()
    rng = random.Random()
    entries = [
        SourceEntry(
            name=item.get("name", ""),
            file=item.get("file", item.get("name", "")),
            timing=[tuple(pair) for pair in item["timing"]],
        )
        for item in sourcemap.get("files", [])
    ]
    if not entries:
        raise ValueError("No entries found in sourcemap.json")

    buckets: dict[str, list[tuple[float, float]]] = {key: [] for key in keys}
    used_indices: set[int] = set()

    rule_map = None
    if rule:
        if isinstance(rule.get("map"), dict):
            rule_map = rule["map"]
        elif isinstance(rule, dict):
            rule_map = rule

    fallback_entry = None
    if rule_map:
        buckets, used_indices, fallback_entry = apply_rule_map(entries, keys, rule_map)

    remaining_entries = [
        entry for idx, entry in enumerate(entries) if idx not in used_indices
    ]

    unassigned_keys = [key for key in keys if not buckets[key]]

    if fallback_entry is not None:
        for key in unassigned_keys:
            buckets[key].extend(fallback_entry.timing[:1])
    else:
        direct_map, remaining_after_match = assign_direct_matches(
            remaining_entries, unassigned_keys
        )
        for key, entry in direct_map.items():
            buckets[key].extend(entry.timing)

        unassigned_keys = [key for key in keys if not buckets[key]]
        rng.shuffle(remaining_after_match)
        assign_round_robin(remaining_after_match, unassigned_keys, buckets)
        fill_empty_with_random(keys, buckets, entries, rng)

    return {key: {"timing": buckets[key]} for key in keys}
