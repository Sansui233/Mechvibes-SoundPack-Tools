## What is sourcemap

sourcemap is about defining a "sound".

a virtual "sound" can be mapped to

- a file
- a file with time selection(ms) (single mode, support key down/up)
- files with time selections(for random play)

the virtual sound 

## Fields

```json5
{
  "audio_file": "sound.ogg",
  "source_dir": "sounds\\bubble",
  "sounds":[
    {
      "name": "soundname" // vitual sound name, is the filename
      "files": [
        {
          "filename.wav": [000,200] // timing in sound.ogg (extension is user-controlled)
        }
      ]
    }
  ]
}
```

## v1 schema

v1 always use the single audio file with timing definition in the project.

## v2 schema

v2 add two features.

- random play. The rule like `{0-3}.wav: [Numpad*]` means the sound is played with one of 3 audio files. 
- key-up matching

## DXv2 schema

DX (MVDX) supports key-down + key-up via timing pairs in a single audio file.

What DX does NOT support (in this tool):
- random play (e.g. `{0-3}.wav` style multi-file selection)

So DX is always single-audio + timestamp-based; `--split` can be used to generate 2 timing pairs (down/up).

## `--split`

if you want to support keydown automatically, add this arg. at this time, a sound should generate the "up" sound. You can't see this is sourcemap, because the `up` sound generated only when packed.

```json
  "audio_file": "sound.ogg",
  "source_dir": "sounds\\bubble",
  "sounds":[
    {
      "name": "soundname" // vitual sound name, default is the same to file name
      "files": [
        {
          "filename.wav": [000,200] // timing in sound.ogg
        }
      ]
    },
    // not in sourcemap.json, but logically exists by `--split` args
    {
      "name": "soundname-up" // vitual sound name
      "files": [
        {
          "filename.wav": [100,200] // timing in sound.ogg
        }
      ]
    }
  ]
```

When generating v2 schema, it will allocated "soundname" randomly to unruled keys as v1, but the *-up key will find the corresponding `soundname-up`. and generate the corresponding file when packing.

- `filename-up.wav` defined in "soundname-up" (file naming uses `-up`, e.g. `1-up.wav`)
- `filename-down.wav` calc the timing by soundname(total area) minus soundname-up(partial area)

the config generates based both on rule and sourcemap.

if {0-3}.wav for numpad0, and `--split` on. 

- on v2, numpad0 keyup should be mapped to "{0-3}-up.wav", keydown should be mapped to "{0-3}-down.wav", and corresponding files should be generated.
- on v1. nothing happens. Just use the original sound(file) timing in single audio file. 
- on DX. {0-3} not supported yet, but use keydown and keyup timing in a single audio file.

## rule

User rule is always prior to --split command