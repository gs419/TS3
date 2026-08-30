# Tower! Simulator 3 — Install & Addon Stack Review

Review of the application copy stored in OneDrive at `Public File Share\Tower! Simulator 3`
(personal copy, used as the base for custom addon development).

## Overview

The folder is a complete, ready-to-run Windows install (~79 GB) of **Tower! Simulator 3**,
FeelThere's Unity-based air traffic control simulator (Steam app `2176130`), plus a custom
voice-control stack layered on top.

Stock game pieces, all present and normal:

- `Tower! Simulator 3.exe` with `Tower! Simulator 3_Data\` and the `MonoBleedingEdge` runtime
- `extwin\` — the external-window viewer app (its own Unity player)
- `TowerDX11.bat` / `TowerDX12.bat` launchers
- Gameplay data: `jobs.csv` (career missions), `scoring.csv`, `lights.cfg`, `light_settings.cfg`

## Content packs

### Airports (77 GB)

17 fields installed: KATL, KAUS, KBDL, KBNA, KBOS, KBUR, KCLE, KCVG, KDAL, KDCA, KDEN,
KDFW, KDTW, KEWR, KFLL, KIAD, KIAH. Most weigh 0.7–4 GB each.

**KEWR is a work-in-progress stub** (~5 MB): it has `package.txt`, a minimap PNG,
`databases\`, and `instruments\`, but no 3D models yet, so it is not playable in its
current state. Its `package.txt` already carries the required structure (ICAO, name,
level, description, `MINIMAP_SCALE`, and `RUNWAY name: posx, posy, rotation, size` lines).

The shared `Airports\` root also carries the voice/phraseology data the game reads:
`airports.csv`, `airlines`-related CSVs, `commands.csv`, `alphabet.csv`, `numbers.csv`,
`responds.csv`, `errors.csv`.

### Airplanes (561 MB)

Default fleet under `Airplanes\default\`: AJT0, BIZ0, BTRP, DPRP, EJT1, FRJ1, plus a
"TGB V2" variant nested under AJT0 — the pattern to follow for aircraft variants.

## Custom voice pipeline

Three home-built modules, each PyInstaller-packaged with a tidy `DEPENDENCY_LICENSES.md`:

- **RECOG (252 MB)** — `recog.exe` + `cpm.exe`. Speech recognition built on
  faster-whisper / CTranslate2 / ONNX Runtime. Serves on `127.0.0.1:9000`, push-to-talk
  on right-Ctrl with VAD-based hypothesis decoding. `cpm` is a fuzzy command matcher
  (threshold 0.6) driven by `config\commands.csv`, `airlines.csv`, `alphabet.csv`,
  `numbers.csv`, `session_lexicon.json`, and `normalization_rules.yaml`. The session
  lexicon auto-includes airline pronunciations and taxiways (min length 3).
- **TTS (610 MB)** — MeloTTS-based `tts.exe` with BERT prosody models and a
  `Feelthere-Custom-Voices` set for controller/pilot voices.
- **Glue at the game root** — `towerspeakbridge.exe` and `TowerRecognizer.dll` connect
  the pipeline to the game; `plugins\miyo.asset` (45 MB) is an add-on asset.

## Findings

1. **Model path mismatch (real bug).** `RECOG\config\config.json` sets
   `model_path: models\medium.en` and `hypo_model_path: models\base.en`, but
   `RECOG\models\` contains only `finetuned_small` (a fine-tuned Whisper small, 253 MB).
   recog will fail on startup from this copy until the config points at
   `models\finetuned_small` or the medium.en/base.en models are added.
2. **`config\hotwords.txt` is empty** while referenced by the config. Harmless, but it
   means hotword boosting is doing nothing — free headroom for addon work: seeding it
   with an addon airport's taxiways, fixes, and airline callsigns should measurably
   improve recognition at that field.
3. **KEWR** needs its models/assets built before it is playable (see above).
4. Minor tidiness: an empty nested `Tower! Simulator 3` folder sits inside the install,
   and `save_ptt_audio_to: "./"` in the recog config will scatter PTT recordings into
   the working directory over time.

## Addon development notes

- **Airport addons** live in `Airports\<ICAO>` with `package.txt`, a minimap PNG,
  `databases\` (schedules, terminals, taxiways), `instruments\` (ADIRS/DBRITE data),
  and the 3D scenery assets. KBDL (~360 MB) is the smallest complete example to crib
  the structure from.
- **Aircraft addons** go under `Airplanes\default\<TYPE>`; the "TGB V2" folder inside
  AJT0 shows the variant pattern.
- **Voice customization** is all data-driven via the RECOG `config\` CSVs and YAML —
  no code changes needed to teach the recognizer new callsigns or taxiways.
