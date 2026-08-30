# TS3 data-interface inventory

## Question and scope

Issue #22 asks which mechanisms in the current locally installed Tower!
Simulator 3 (TS3) build make game-produced data observable outside `Player.log`,
and what evidence limits each conclusion. It is an evidence inventory, not an
integration specification, protocol publication, or TowerGlance-viability
decision.

The research covers TS3 build `v1.5.180.661s HDRP AI HOTFIX 2` and evidence
collected on 2026-08-02–03. Its exercised scenario matrix was: settings and
menu; active single-player with user-executed aircraft operations; one
external-window instance with four panels followed by an overlapping second
instance; multiplayer list, host, and lobby; a TS3 restart; and bounded
observations of external-app leads. It excludes raw traffic, proprietary bulk,
payload keys or schema, credentials, personal/profile data, operational
identifiers, absolute paths, and third-party code, assets, installation
content, private streams, logs, or UI/product labels.

Documentary and static review preceded runtime probing. Runtime phases then
tested the mechanism candidates and lifecycle assumptions found by that review;
external-app observations were performed last and could produce hypotheses
only, never evidence authority.

The ledger is mechanism-based, not a list of examples. Each status is scoped
to this build, exercised timing, and available privileges; it cannot prove
absence in another mode or future build.

An independent-public-source screen was also completed. The screened SteamDB
patch index is explicitly unaffiliated with Valve/Steam and mirrors the Update
7 announcement; it supplies a time/build-index lead only, not an independent
TS3 interface claim. No technical interface conclusion in this inventory relies
on it; concrete TS3 conclusions remain independently confirmed locally or by
the primary sources cited below. [S10][L5]

## Direct answer

**Yes.** The current local TS3 build produces observable game data beyond
`Player.log` through a **game-owned loopback TCP listener** on the selected
Communication Port. The observed local port was `12030`. It was active in live
single-player and was used by the main TS3 process and game-owned `extwin`,
`cpm`, `recog`, and `tts` processes. It was absent in settings/menu and closed
on the observed multiplayer transition.

The strongest independent game-owned route is `extwin`: two concurrent
external-window processes connected to that listener and visibly rendered live
game panels. FeelThere's developer hotfix independently names “ADIRS on the
external window.” [S4]

This establishes a game-owned transport/output route, not a public API or a
safe read-only client. The listener was bidirectional. No official public TS3
document found here describes the Communication Port, an
`extwin`/`cpm`/`recog`/`tts` protocol, a supported external client, payload
schema, or multiplayer-port contract.

## Observed evidence

### Game-owned Communication Port and external window

- In live single-player, a game-owned loopback listener was active on the
  selected Communication Port (`12030` in the observed sessions). Settings
  exposed multiple fixed choices; their full list is deliberately not
  published. The listener was loopback-only in the observations.
- The TS3 main process and game-owned `extwin`, `cpm`, `recog`, and `tts`
  helpers used connections associated with the listener. This establishes
  process ownership, correlated lifecycle, transport, and bidirectionality;
  it does not establish authorization or client semantics.
- Two `extwin` instances were simultaneously connected and visibly rendered
  live game panels. This is independent of external-app leads.
- The retained format signature deliberately contains no content: 5,000 TCP
  payload frames totalling 3,129,262 bytes; printable ratio 1.0; 3,331
  JSON-like frame starts and 3,331 newline-terminated payload frames; null
  ratio 0; TLS/compression magic 0; entropy 4.814 bits/byte. It supports only
  a bounded printable/JSON-like framing inference. TCP segmentation leaves
  record boundaries, request/response pairing, message completeness, schema,
  and field meaning unknown.
- A separate static loopback configuration candidate was found, but had no
  matching runtime listener or connection; it remains unconfirmed.

### Multiplayer candidates and external-app leads

- Remote TCP `8080` was observed in list/menu. TCP `8081` appeared in
  host/lobby and closed on return, while `8080` remained; UDP endpoint families
  changed across multiplayer phases. Service ownership, peer identity,
  protocol, authentication, direction, and relevance remain unknown.
- External-app logs and variants are not sources or dependencies. They yielded
  non-authoritative hypotheses only: one external app directly connected to
  the independently confirmed game listener; another simultaneously held a
  local game-listener connection and remote TLS connection. Only the
  independently confirmed TS3-owned listener and `extwin` route supports the
  conclusion in this inventory.

### Files, diagnostics, and processes

- Main and external-window `Player.log` files are game-owned diagnostics, not
  an authoritative Operational Session contract. Official support distinguishes
  current and previous log-family roles. [S1]
- Process creation and game-owned helper roles were observed. A temporary
  helper-extraction class was observed but did not provide a convincing
  additional game-data channel.
- No convincing additional file channel was found in the exercised scenarios.
  That bounded observation is not a claim that another mode or timing cannot
  create one.

## Evidence-led coverage ledger

| Mechanism class | Status | Evidence and minimal signature | Limitations / boundary |
| --- | --- | --- | --- |
| Current diagnostic log family | **observed interface with output** | File-based, game-to-file append/reset text output, discovered through persistent-file observation and read-only structural inspection. One bounded snapshot contained 5,580 lines mixing engine/application diagnostics, structured configuration or persisted-state blocks, networking or speech diagnostics, and game-related text; file order supplied only weak sequence evidence. [L1][L2][S9] | Undocumented mixed diagnostics with incomplete/non-monotonic timestamps; not an authoritative live-state schema or stable session/event contract. |
| Previous diagnostic log family | **observed interface with output** | File-based, game-to-file rotated prior-session text output, discovered through official support documentation and local file-lifecycle observation. [S1][L1][S9] | Same diagnostic family and a prior-session snapshot, not a separate live feed; rotation, completeness, and session-boundary semantics remain undocumented. |
| Generated child configuration | **candidate requiring a separate probe** | Static game-owned child/configuration role observed. [L1] | Lifecycle and game-produced output were not established. |
| Static airport/database/instrument resources | **irrelevant because it exposes no game-produced data** | Static local input resources were inventoried. [S8] | Do not establish active-session selection, linkage, or output. |
| Other generated user state, saves, temp, cache | **investigated but not observed** | File/process coverage did not reveal a convincing extra channel. [L1][L2] | Scenarios, timing, roots, and modes remain incomplete. |
| Crash dump / bug-report package | **candidate requiring a separate probe** | Official Update 7 describes radio-log and bug-report features. [S2] | Triggering output was outside this safety-stopped runtime work. |
| Game-owned AI/speech/helpers (`cpm`/`recog`/`tts`) | **candidate requiring a separate probe** | Process roles and loopback connections observed in live single-player. [L2] | Audio/speech and operational-state semantics, framing, and direction unknown. |
| Game-owned TCP listener (Communication Port) | **observed interface with output** | Live loopback `12030` listener; process/lifecycle correlation and bounded output signature. [L2][L3] | Bidirectional; handshake, permissions, schema, and safe external consumption unknown. |
| Built-in external display (`extwin`) | **observed interface with output** | Game-owned presentation/stream mechanism: two concurrent TS3-owned clients connected to the listener and visibly rendered live multi-panel output. Game-to-`extwin` output was present inside a bidirectional connection; the content-free aggregate signature is reported above, and official material corroborates an external ADIRS display. [L2][L3][S4] | Screen/payload correspondence, request/response roles, record boundaries, schema, and field meaning remain unknown. |
| UDP | **candidate requiring a separate probe** | Endpoint families changed across multiplayer phases. [L2] | No payload, direction, peer, or game-produced content established. |
| Multiplayer remote network | **candidate requiring a separate probe** | Remote TCP `8080`/`8081` lifecycle and UDP-family changes observed. [L2] | No official TS3 port/protocol docs; no active remote interaction. |
| Named pipes | **investigated but not observed** | Owner-attribution coverage did not establish a persistent TS3 pipe lead. [L2] | Snapshot method cannot exclude timing-, handshake-, or privilege-dependent pipes. |
| Shared memory / memory-mapped files / anonymous IPC | **investigated but not observed** | Handle/object snapshots did not establish an attributed lead. [L2] | Snapshot evidence cannot prove absence; object names/content were not read. |
| Windows messages / window handles | **candidate requiring a separate probe** | Game-owned external windows were observed. [L2] | No message inspection or injection; no data route established. |
| Process modules | **investigated but not observed** | Role-level module inventory did not establish data publication. [L1][L2] | Modules are capability context, not a data contract. |
| Process handles | **investigated but not observed** | Sanitised handle snapshots were used for attribution only. [L2] | No object content/name reading; snapshot cannot prove absence. |
| Windows services / scheduled tasks | **investigated but not observed** | Static and runtime ownership coverage found no convincing game-data route. [L1][L2] | Other installation locations, privileges, and builds remain open. |
| Registry / OS configuration | **investigated but not observed** | TS3-filtered static configuration coverage found no data-publication route. [L1] | Installer and unexercised mode effects remain open. |
| Unity diagnostics / debug / console | **candidate requiring a separate probe** | Unity/player diagnostics explain the already-counted log family. [S7][L1] | No separate TS3 output interface established; do not change logging settings. |
| Plugin / extension / mod / Add-ons | **investigated but not observed** | Static/runtime coverage and visible Add-ons surface did not establish a game-data route. [L1][L2][S3] | Visible emptiness cannot prove hidden, disabled, future, or external absence. |
| In-game radio message log | **candidate requiring a separate probe** | Official Update 7 documents an in-game radio log. [S2] | No externally observable artifact/transport was established. |
| Platform / cloud / achievements / overlay | **irrelevant because it exposes no game-produced data** | No TS3-published operational-data route was established. [S3][S6] | Do not query accounts, cloud, auth, or third-party services. |
| Local HTTP / WebSocket / other services | **investigated but not observed** | Socket coverage outside the confirmed listener found no separate route. [L2] | Confirmed listener is not classified as HTTP/WebSocket; no active probe. |

## Engineering inference

1. The live loopback listener and concurrent game-owned `extwin` consumers are
   strong evidence of a TS3-internal game-data route beyond `Player.log`. This
   is stronger than an external-app correlation because producer, consumers,
   lifecycle, and visible panels were independently TS3-owned.
2. The quantitative format signature supports only a tentative printable,
   JSON-like framing hypothesis. TCP segmentation means it is not a record or
   schema specification.
3. The AI/helper boundary may carry speech or other game-adjacent data, but
   process/connection correlation does not prove content or a separable audio
   interface.
4. TCP `8080`/`8081` and UDP changes show a multiplayer network surface, not a
   local data interface. Valve's Steam Networking documentation describes
   relay/UDP platform possibilities; it does not prove TS3 uses Steam Datagram
   Relay or a specific implementation. [S6]

## Maintainer decision

- Do not treat any route as a public TS3 API, stable contract, or demonstrated
  TowerGlance input. Issue #22 does not claim TowerGlance viability.
- A future local client must be TowerGlance-owned, separately authorised,
  narrowly bounded, sanitised, and designed for bidirectional risk. No
  external-app implementation or stream may become a dependency or authority.
- All live runtime follow-up is suspended until a separate shutdown-safety
  method is established.

## Completeness argument and residual uncertainty

The scenario matrix exercised settings/menu, active single-player with user
operations, external-window overlap, multiplayer list/host/lobby, restart, and
bounded external leads. The ledger explicitly covers file/log families,
generated state, static resources, crash output, AI/audio helpers, TCP/UDP,
multiplayer, pipes/shared state, windows/messages, modules/handles,
services/tasks, registry, Unity diagnostics, extensions, radio output,
platform surfaces, and local web/service hypotheses. This is materially broader
than Player.log or a single TCP observation.

It is not mathematical exhaustiveness. Residual uncertainty includes
event-/timing-dependent and handshake-required paths, inaccessible or
privileged mechanisms, unexercised modes/settings, payload schema/identity,
record ordering/freshness, permissions, write semantics, and version stability.

## Safety stop

Repeated hangs/exits occurred around tool shutdown. In the last clean run, the
sampler completed about 1.3 seconds after its last game sample and TS3
disappeared around capture shutdown. Causality is unknown, but the shutdown
sequence/tooling combination is a credible safety suspect. Raw local logs are
retained by explicit instruction for later separate crash analysis. No live
instrumentation or further probe may proceed until dedicated validation of safe
capture-tool start, stop, and cleanup establishes a safe method; this makes no
crash-cause, user-blame, or Escape inference.

## Ranked follow-up candidates

1. **Dedicated capture-tool shutdown-safety validation — prerequisite.**
   Establish safe capture-tool start, stop, and cleanup before any new live
   observation. This prerequisite does not investigate or assign the game's
   crash root cause.
2. **Bounded TowerGlance-owned Communication Port handshake/read prototype —
   only after safety.** Define stop conditions and bidirectional threat model;
   retain only minimal sanitised evidence and stop before schema decoding or
   write-capable actions.
3. **Owner-attributed pipe/shared-object/window-message study.** Improve
   attribution without opening pipes, reading objects, or injecting messages.
4. **Multiplayer remote-network semantics.** Investigate only after safety and
   separate explicit authority; keep remote service interaction out of scope
   unless specifically approved.
5. **Radio/bug-report/generated-output study.** Separately authorise any GUI
   action that can generate files; retain only sanitised derived evidence.

No issue is created by these candidates, and none independently demonstrates
TowerGlance viability.

## Sources

### Primary/public sources

- **S1 — FeelThere Support:** [How to obtain your game log
  files](https://feelthere.zendesk.com/hc/en-us/articles/18584181148188-How-to-obtain-your-game-log-files)
  (current and previous `Player.log` roles).
- **S2 — official Update 7:** [Major Tower Simulator 3 Update
  7](https://steamcommunity.com/games/2176130/announcements/detail/681878780522793839)
  (radio message log and bug-report feature).
- **S3 — official Steam store listing:** [Tower! Simulator 3](https://store.steampowered.com/app/2176130/Tower_Simulator_3/)
  (local voice/recognition, Online Co-op, and customization claims; not an API
  specification).
- **S4 — FeelThere developer hotfix:** [HOTFIX RELEASED! Details
  inside](https://steamcommunity.com/app/2176130/discussions/0/591760110786775954/)
  (explicitly names ADIRS on the external window).
- **S5 — official TS3 announcements:** [Tower! Simulator 3
  announcements](https://steamcommunity.com/app/2176130/announcements/)
  (current official update surface; no port/protocol specification found).
- **S6 — Valve platform documentation:** [Steam
  Networking](https://partner.steamgames.com/doc/features/multiplayer/networking)
  (relay/UDP platform possibilities, not TS3-use evidence).
- **S7 — Unity documentation:** [Log files](https://docs.unity3d.com/Manual/log-files.html)
  (general engine log behaviour, not a TS3 schema).
- **S8 — repository evidence:** [installed airport and schedule coverage](ts3-installed-airport-schedule-data-coverage.md)
  (static-resource scope).
- **S9 — canonical earlier evidence:** [issue #4 result comment](https://github.com/CrankyAnt/TowerGlance/issues/4#issuecomment-5156717657)
  and [Player.log lifecycle coverage](ts3-player-log-event-lifecycle-coverage.md)
  (prior bounded log/process evidence).
- **S10 — independent public technical lead, negative screen:** [SteamDB Update
  7 patch index](https://steamdb.info/patchnotes/23732564/) (an unaffiliated
  build/patch index that reproduces the official Update 7 text; no independent
  TS3 port, protocol, payload, or interface claim was found or relied on).

### Sanitised local provenance

- **L1 — documentary/static review, 2026-08-02–03:** game-owned settings,
  static resources, diagnostic roles, component/configuration roles, modules,
  services/tasks, registry, and Unity context. Supports static-class and
  configuration rows; excludes code, raw paths, binary details, and content.
- **L2 — runtime lifecycle/socket/handle observation, 2026-08-02–03:** menu,
  settings, active single-player with user operations, external-window overlap,
  multiplayer list/host/lobby, return, and restart. Supports lifecycle,
  listener, port, process, UDP/multiplayer, pipe/shared-object/handle and
  window rows; excludes active remote interaction, object reads, or injection.
- **L3 — bounded external-window transport sample, 2026-08-03:** 5,000-frame
  aggregate signature only. Supports bidirectionality and the stated format
  metrics; excludes raw payload, schema, keys, records, and message semantics.
- **L4 — bounded external-app lead observation, 2026-08-03:** connection-role
  correlation only. Supports hypothesis prioritisation, never TS3 protocol or
  implementation claims; excludes external logs, code, UI, product details,
  private streams, and dependencies.
- **L5 — independent-public-source screen, 2026-08-03:** checked the S10
  SteamDB patch/build index against the official Update 7 announcement. Supports
  only the documented negative result: it did not add an independent interface
  claim and was not promoted beyond a hypothesis/time-index lead.
