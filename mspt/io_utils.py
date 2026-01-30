from __future__ import annotations

import json
from pathlib import Path


def _strip_json5_comments(text: str) -> str:
    """Strip // and /* */ comments while preserving string literals."""

    out: list[str] = []
    i = 0
    in_string = False
    string_quote = ""
    escape = False

    while i < len(text):
        ch = text[i]

        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == string_quote:
                in_string = False
                string_quote = ""
            i += 1
            continue

        if ch in ('"', "'"):
            in_string = True
            string_quote = ch
            out.append(ch)
            i += 1
            continue

        # Line comment
        if ch == "/" and i + 1 < len(text) and text[i + 1] == "/":
            i += 2
            while i < len(text) and text[i] not in ("\n", "\r"):
                i += 1
            continue

        # Block comment
        if ch == "/" and i + 1 < len(text) and text[i + 1] == "*":
            i += 2
            while i + 1 < len(text) and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2 if i + 1 < len(text) else 0
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def _strip_trailing_commas(text: str) -> str:
    """Remove trailing commas before } or ] (common in JSON5-style files)."""

    out: list[str] = []
    i = 0
    in_string = False
    string_quote = ""
    escape = False

    while i < len(text):
        ch = text[i]

        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == string_quote:
                in_string = False
                string_quote = ""
            i += 1
            continue

        if ch in ('"', "'"):
            in_string = True
            string_quote = ch
            out.append(ch)
            i += 1
            continue

        if ch == ",":
            j = i + 1
            while j < len(text) and text[j] in (" ", "\t", "\n", "\r"):
                j += 1
            if j < len(text) and text[j] in ("]", "}"):
                i += 1
                continue

        out.append(ch)
        i += 1

    return "".join(out)


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")

    # Prefer json5 if installed (full JSON5 support), otherwise do best-effort
    # comment + trailing comma stripping.
    try:
        import json5  # type: ignore

        return json5.loads(raw)
    except ModuleNotFoundError:
        cleaned = _strip_trailing_commas(_strip_json5_comments(raw))
        return json.loads(cleaned)


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
