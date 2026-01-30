from __future__ import annotations

from typing import cast

import pytest

from mspt.converters import build_mechvibes_v2_inputs, to_mechvibes_v1, to_mechvibes_v2
from mspt.schema.mvdx import DefinitionKey, KeyName, MVDXSchema


def test_mechvibes_v1_merges_keyup_timings() -> None:
    definitions = cast(
        dict[KeyName, DefinitionKey],
        {
            "Enter": DefinitionKey(timing=[(0.0, 10.0), (10.0, 20.0)]),
        },
    )
    mvdx = MVDXSchema(
        audio_file="sound.ogg",
        config_version="2",
        created_at="2025-01-01T00:00:00Z",
        id="test",
        name="Test",
        definitions=definitions,
    )
    v1 = to_mechvibes_v1(mvdx=mvdx)
    # Uses a single clip spanning down+up.
    assert v1.defines["28"] == [0, 20]


def test_mechvibes_v1_clip_conversion() -> None:
    definitions = cast(
        dict[KeyName, DefinitionKey],
        {
            "Enter": DefinitionKey(timing=[(100.4, 200.4)]),
            "Tab": DefinitionKey(timing=[(0.0, 10.0)]),
        },
    )
    mvdx = MVDXSchema(
        audio_file="sound.ogg",
        config_version="2",
        created_at="2025-01-01T00:00:00Z",
        id="test",
        name="Test",
        definitions=definitions,
    )
    v1 = to_mechvibes_v1(mvdx=mvdx, includes_numpad=False)
    assert v1.version == 1
    assert v1.key_define_type == "single"
    assert v1.sound == "sound.ogg"
    assert v1.includes_numpad is False
    # Enter keycode is 28 in Mechvibes keycodes
    assert v1.defines["28"] == [100, 100]
    assert v1.defines["15"] == [0, 10]


def test_mechvibes_v2_up_suffix_rule_sets_up_defines() -> None:
    sourcemap = {
        "audio_file": "sound.ogg",
        "files": [
            {"name": "Enter", "file": "1.wav", "timing": [[0.0, 100.0]]},
            {"name": "Tab", "file": "2.wav", "timing": [[100.0, 200.0]]},
            {"name": "misc", "file": "0.wav", "timing": [[200.0, 300.0]]},
            {"name": "misc", "file": "3.wav", "timing": [[300.0, 400.0]]},
        ],
    }
    rule = {
        "map": {
            "1.wav": ["Enter", "Tab"],
            "{0-3}.wav": ["Numpad*_UP", "*_UP"],
        }
    }

    inputs = build_mechvibes_v2_inputs(sourcemap=sourcemap, rule=rule, split=False)
    assert inputs.has_keyup_rules is True
    assert inputs.sound == "1.wav"  # fallback picked from first '*' match
    assert inputs.soundup == "{0-3}.wav"

    v2 = to_mechvibes_v2(
        id="test",
        name="Test",
        sound=inputs.sound,
        soundup=inputs.soundup,
        keydown_defines=inputs.keydown_defines,
        keyup_defines=inputs.keyup_defines,
        all_keys=inputs.keydown_defines.keys(),
        fill_missing_up=True,
    )

    assert v2.version == 2
    assert v2.key_define_type == "multi"
    # Enter down is defined
    assert v2.defines["28"] == "1.wav"
    # Enter up falls back to soundup
    assert v2.defines["28-up"] == "{0-3}.wav"
    # One of the numpad keys should also get keyup define
    assert v2.defines["82-up"] == "{0-3}.wav"  # Numpad0


def test_mechvibes_v2_split_derives_up_from_down() -> None:
    sourcemap = {
        "audio_file": "sound.ogg",
        "files": [
            {"name": "Enter", "file": "1.wav", "timing": [[0.0, 100.0]]},
            {"name": "Tab", "file": "2.wav", "timing": [[100.0, 200.0]]},
            {"name": "misc", "file": "0.wav", "timing": [[200.0, 300.0]]},
        ],
    }

    inputs = build_mechvibes_v2_inputs(sourcemap=sourcemap, rule=None, split=True)
    assert inputs.has_keyup_rules is True
    # Enter down uses its own file, so Enter up should follow it.
    assert inputs.keydown_defines["Enter"] == "1.wav"
    assert inputs.keyup_defines["Enter"] == "1-up.wav"
