from __future__ import annotations

import random
import re
from fnmatch import fnmatchcase
from pathlib import Path
from typing import get_args

from mspt.io_utils import read_json
from mspt.models import SourceEntry
from mspt.schema.mvdx import KeyName
from mspt.sourcemap import iter_sourcemap_entries


def to_list(value) -> list[str]:
    """Normalize a rule selector value into a list of selector strings.

    **Input**
    - `value`: selector value from rule JSON. Accepts `None`, `str`, `list[str]`,
      or any iterable of strings.

    **Output**
    - Returns a `list[str]`.

    **Side effects**
    - None.

    **Example**
    - `ensure_list("Enter") -> ["Enter"]`
    - `ensure_list(["Enter", "Tab"]) -> ["Enter", "Tab"]`
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return list(value)


def compile_matcher(pattern: str):
    """Build a case-insensitive matcher for filenames/keys.

    Matching order:
    1) If pattern contains numeric brace ranges like `{0-3}`, expand into a list
       and match using glob for each expanded pattern.
    2) Else, try to compile as regex (re.IGNORECASE) and use `search()`.
    3) If regex compilation fails, fall back to glob matching.

    **Example**
    - `m = compile_matcher("2{0-3}.wav")`
    - `m("20.wav") == True`, `m("24.wav") == False`
    """
    brace_range = re.compile(r"\{(\d+)-(\d+)\}")
    if brace_range.search(pattern):
        expanded: list[str] = [pattern]
        while True:
            next_expanded: list[str] = []
            did_expand = False
            for item in expanded:
                match = brace_range.search(item)
                if not match:
                    next_expanded.append(item)
                    continue
                did_expand = True
                start = int(match.group(1))
                end = int(match.group(2))
                if start > end:
                    start, end = end, start
                for num in range(start, end + 1):
                    next_expanded.append(
                        item[: match.start()] + str(num) + item[match.end() :]
                    )
            expanded = next_expanded
            if not did_expand:
                break

        return lambda text: any(fnmatchcase(text.lower(), p.lower()) for p in expanded)

    try:
        regex = re.compile(pattern, re.IGNORECASE)
        return lambda text: regex.search(text) is not None
    except re.error:
        return lambda text: fnmatchcase(text.lower(), pattern.lower())


def load_key_names() -> list[str]:
    """Return all supported key names.

    **Input**: none.
    **Output**: a stable list of KeyName literal strings.
    """
    return list(get_args(KeyName))


def resolve_key_selectors(selectors: list[str], keys: list[str]) -> list[str]:
    """Expand key selectors into concrete key names, preserving rule order.

    Resolution:
    - If selector equals a key name, it is appended.
    - Otherwise selector is treated as regex/glob (via `compile_matcher`) and
      expanded to all matching keys (in `keys` order).
    - Duplicates are removed while preserving first occurrence order.

    **Inputs**
    - `selectors`: e.g. `["Enter", "Numpad*"]`
    - `keys`: the full key name universe.

    **Output**
    - Concrete key list.
    """
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
    """Load a rule JSON/JSON5 file from disk."""
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
    """Apply rule map to source entries and build per-key timing buckets.

    Inputs
    - entries: ordered `SourceEntry` list from sourcemap.
    - keys: full key universe.
    - rule_map: mapping of `filePattern -> selectors`.

    Returns
    - buckets: dict of key -> list of timing pairs (max 2 pairs per key).
    - used_indices: set of entry indices consumed by earlier rules.
    - fallback_entry: the first matched entry whose selector list contained `"*"`.

    Mutations / behavior
    - `used_indices` grows as file patterns match entries; later patterns cannot
      reuse already-used entries.
    - `buckets[key]` gets timing pairs appended for each matched entry.
    """

    buckets: dict[str, list[tuple[float, float]]] = {key: [] for key in keys}
    used_indices: set[int] = set()
    fallback_entry: SourceEntry | None = None

    for pattern, selectors in rule_map.items():
        selector_list = to_list(selectors)
        has_fallback = "*" in selector_list
        if has_fallback:
            selector_list = [item for item in selector_list if item != "*"]

        matcher = compile_matcher(pattern)
        target_keys = resolve_key_selectors(selector_list, keys)

        for idx, entry in enumerate(entries):
            if idx in used_indices:
                continue
            if not matcher(entry.file):
                continue

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
    """Assign entries to keys by exact `entry.name == key` (case-insensitive).

    **Inputs**
    - `remaining_entries`: entries not used by the rule engine.
    - `candidate_keys`: currently-unassigned keys.

    **Outputs**
    - `direct_map`: mapping of matched key -> entry
    - `remaining_after_match`: entries that did not match any key
    """
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
    """Assign remaining entries to remaining keys in a stable round-robin order.

    **Inputs**
    - `remaining_entries`: shuffled candidate entries.
    - `candidate_keys`: list of currently-unassigned keys.
    - `buckets`: per-key timing buckets.

    **Output**
    - None.

    **How state changes**
    - Mutates `buckets`: for each entry, appends its first timing pair into the
      next available key's bucket.
    - Does not modify `remaining_entries` or `candidate_keys` in-place.

    **Example**
    - candidate_keys = ["A", "B"], remaining_entries = [e1, e2]
    - After call: buckets["A"] += e1.timing[:1], buckets["B"] += e2.timing[:1]
    """
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
    """Fill any still-empty keys by random selection from existing entries.

    **Inputs**
    - `keys`: all keys.
    - `buckets`: existing assignments.
    - `entries`: all available entries.
    - `rng`: random source.

    **Output**
    - None.

    **How state changes**
    - Mutates `buckets` by appending a single timing pair to any key that is
      still empty.
    - Prefers `entries` whose `entry.name` is *not* a key name (so files like
      `enter.wav` don't get reused as generic samples unless there are no
      alternatives).
    """
    reserved_names = {k.lower() for k in keys}
    candidates = [
        entry
        for entry in entries
        if entry.name and entry.name.lower() not in reserved_names
    ]
    if not candidates:
        candidates = entries
    for key in keys:
        if not buckets[key]:
            pick = rng.choice(candidates)
            buckets[key].extend(pick.timing[:1])


def build_definitions(sourcemap: dict, rule: dict | None) -> dict[str, dict]:
    """Build MVDX-style definitions (timing pairs) from sourcemap + optional rule.

    **Inputs**
    - `sourcemap`: parsed `sourcemap.json` with `files[].timing`.
    - `rule`: parsed rule dict (or None).

    **Output**
    - `dict[keyName, {"timing": [(start,end), ...]}]` for all supported keys.

    **How it assigns (high-level)**
    1) Initialize empty buckets for every key.
    2) If rule exists, apply it first; matched entries become unavailable.
    3) If rule provided a fallback entry (`"*"`), fill all remaining keys with it.
    4) Otherwise:
       - direct match by `entry.name == key`
       - reserve key-named entries from being reused as generic pool
       - round-robin remaining entries into remaining keys
       - random-fill any still-empty keys

    **Side effects**
    - None outside the function; output is newly constructed.
    """
    keys = load_key_names()
    rng = random.Random()
    entries = iter_sourcemap_entries(sourcemap)
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

        # Reserve any entries whose name explicitly matches a key name, so they
        # don't get reused as generic samples unless a rule mapped them.
        reserved_names = {k.lower() for k in keys}
        remaining_after_match = [
            entry
            for entry in remaining_after_match
            if not entry.name or entry.name.lower() not in reserved_names
        ]

        unassigned_keys = [key for key in keys if not buckets[key]]
        rng.shuffle(remaining_after_match)
        assign_round_robin(remaining_after_match, unassigned_keys, buckets)
        fill_empty_with_random(keys, buckets, entries, rng)

    return {key: {"timing": buckets[key]} for key in keys}
