# Tower! Simulator 3 — Source Code, SDK & Documentation Resources

Findings from a web/GitHub survey (August 2026). The game itself is proprietary
(no public source), but there is an official SDK, an official manual, a confirmed
live data source (Player.log), and an active community-tool ecosystem on GitHub.

## Official (FeelThere)

- **SDK** — Unity-based airport SDK with an `AirfieldEditor` game object that
  loads `.airport` files; distributed via feelthere.com. A free public
  **Airplane Exporter SDK** exports Unity aircraft models into the game.
- **Start Guide / manual (PDF)** —
  <https://feelthere.com/wp-content/uploads/2022/12/Start-Guide-Basics-for-Tower-Simulator-3.pdf>
- **Customization dev blog** (terminal cfg, strips CSVs, schedules) —
  <https://feelthere.com/tower-simulator-developer-blog-5/>
- **Bug tracker** — <https://tower-simulator-3-bugs.nolt.io/>
- Community guidance: edit CSVs with Notepad++ (not Excel), always keep backups.

## Live data source (confirmed)

Unity `Player.log` at `%AppData%\..\LocalLow\FeelThere_*\Tower! Simulator 3\Player.log`
(plus `Player-prev.log` for the previous session). Community companion apps parse
this file in real time; FeelThere support also asks for it in bug reports.

## Community tools on GitHub

- `RagingLightning/TS3CallsignHelper` (C#, GPL-3.0) — real-time helper, modular
  (Api/Game/Wpf/Modules)
- `CrankyAnt/TowerGlance` — "independent local-first real-time webview"
- `cjpitre/TrafficVisualizer` (C#) — schedule/traffic visualization
- `saintwolf/_TowerSimulator3_VoiceTrainer` (C#) — voice command trainer
- `2BeK/ts3-acl` (Python) — airline callsign lookup
- `theVosCache/Tower-Simulator-3-Instrument-Customizer` (PHP) — instrument
  strip customization
- `manuel3108/tower-simulator-3-extensions` (Svelte)
- `MyVizDrake/Espanso_TS3` — Espanso text-expansion configs for commands

## Community tools elsewhere

- **OSM2Airport** — generates validated `.airport` files from OpenStreetMap for
  the official SDK (tutorials on YouTube: "Make an airport for Tower! Simulator 3
  with the SDK and OSM2Airport")
- **T3Scheduler** (jareksastro.org/T3Scheduler) — random schedule generator,
  imports real-world schedules from FlightAware
- **TowerCompanion** (towercompanion.com) — companion overlay app
- **CuratedPile's tools** (clapit.icu/curatedpile) — misc tools/mods incl.
  TrafficVisualizer builds
- **Nyerges Design** (nyergesdesign.com) — official third-party airport/traffic
  addon developer (World Traffic & Color bundle)
- simFlight forums host the FeelThere ATC community (older "Tower!3D Pro Tools"
  thread covers the predecessor's file formats, much of which carried forward)
- towersim3editors.com — defunct (tools discontinued ~March 2024)
