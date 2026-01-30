Mechvibes SoundPack Tools
===========================

Language: English | [简体中文](README_CN.md) | [日本語](README_JP.md)

This tool automates Mechvibes SoundPack generation. In the simplest case, run
`mspt -i <your sound directory>` and the soundpack will appear under target.

## 1. Requirements

- [ffmpeg](https://www.ffmpeg.org/) (must be available in PATH)
- [Python](https://www.python.org/) (recommend using [uv](https://docs.astral.sh/uv/))

### Install (required for mspt)

```
# activate your Python environment, then install this project
pip install -e .
```

## 2. Author

Set the author in rule/common.json:

```json
{
	"author": "YourName"
}
```

## 3. Usage

One-shot (sound.ogg + sourcemap.json + config.json):

```py
mspt -i <your sound directory>
```

Step-by-step:

```py
# step1: generate sound.ogg + sourcemap.json
mspt prepare -i <your sound directory>

# step2: generate config.json from sourcemap.json
mspt build -i target/<soundpack>
```

Packaging:

```py
mspt -i <your sound directory> --release
# or
mspt pack -i target/<soundpack>
```

## 4. Options

One-shot and build share the following options:

```
# Use a rule file to map audio files to keys
mspt -i <your sound directory> --rule rule/example.rule.json

# Split timing into keydown/keyup halves
mspt build -i target/<soundpack> --split

# Auto pack to zip under target
mspt -i <your sound directory> --release

# DX compatibility: emit Mechvibes v1/v2 `version` as strings ("1" / "2")
mspt -i <your sound directory> --dx-compatible
```

## Known issue

This project implements config schemas according to the Mechvibes wiki:
https://github.com/hainguyents13/mechvibes/wiki/Config-Versions

However, in real-world testing we found some MechvibesDX builds have a type-parsing bug for the `version` field.
It may show “import succeeded” but the pack is not actually imported.

If you need to import Mechvibes v1/v2 packs into Mechvibes, use `--dx-compatible` so v1/v2 emit `"version": "1"` / `"version": "2"`.

## Default mapping

Audio files named after keys (e.g. `enter.wav`) map to the corresponding key
(case-insensitive). Key names are defined in [v2.py](./mspt/schema/v2.py).

Other files are assigned to remaining keys with a balanced random strategy.

## Rule format

The rule file contains only a map object. See [rule/example.rule.json](rule/example.rule.json).

- map: audio file -> keynames mapping list (regex or glob supported)
- When the key list contains "*", that audio becomes the fallback: all unassigned keys
	use this audio; otherwise the default random strategy is used.

Example:

```json
{
	"map": {
		"1.wav": ["Enter", "Tab"],
		"2.wav": ["Numpad0", "Numpad*"],
		"fallback.wav": ["*"]
	}
}
```

Both key names and filenames support regex or glob matching.

## Packaging

Packaging zips everything under `target/<soundpack>` except sourcemap.json into a
zip file under target.

```py
# Auto pack after one-shot or build
mspt -i <your sound directory> --release

# Or use the pack subcommand
mspt pack -i target/<soundpack>
```
