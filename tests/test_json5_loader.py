from __future__ import annotations

from pathlib import Path

from mspt.io_utils import read_json


def test_read_json_supports_line_comments(tmp_path: Path) -> None:
    p = tmp_path / "rule.json"
    p.write_text(
        '{\n  // comment\n  "map": {\n    "1.wav": ["Enter"], // trailing\n  },\n}\n',
        encoding="utf-8",
    )
    data = read_json(p)
    assert data["map"]["1.wav"] == ["Enter"]


def test_read_json_supports_block_comments(tmp_path: Path) -> None:
    p = tmp_path / "rule.json"
    p.write_text(
        '{\n  /* block */\n  "map": {"1.wav": ["Enter"]}\n}\n',
        encoding="utf-8",
    )
    data = read_json(p)
    assert data["map"]["1.wav"] == ["Enter"]
