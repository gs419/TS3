# Tower! Simulator 3 Player.log event and lifecycle coverage

## Question and scope

Which v1-relevant session, aircraft, flight, clearance, runway, terminal, failure, and restart observations can be independently recovered from the Tower! Simulator 3-owned `Player.log`; how stable, unique, ordered, and recoverable are they; and which gaps require controlled live scenarios?

This is a clean-room, read-only examination of one current local game log. It does not inspect, use, or compare any third-party companion application. The raw log is private evidence: this report deliberately contains no raw lines, user data, absolute paths, endpoint data, or real in-game identifiers.

## Findings

### Evidence quality and ordering

**Observed.** The examined log has 5,580 lines. It mixes engine/application diagnostics, structured configuration or persisted-state blocks, networking or speech-service diagnostics, and game-related text. It is not a documented event stream or a line-delimited, versioned event schema.

**Observed.** 1,105 lines (about 20 percent) have a recognizable time-of-day prefix. The timestamped subsequence spans about 5.2 hours and has one backward time transition. The largest interval without a recognized timestamp is 929 lines. The file's append order is therefore usable as weak sequence evidence, but it is not a complete, globally monotonic wall-clock ordering.

**Inference.** A consumer may preserve raw file order for diagnostics, but must not infer a total temporal order, a unique game session, or causal ordering from it. A per-record source offset can be retained as evidence; it is not an event identity.

### v1 observation matrix

| v1 concern | Independently recoverable from this log | Stability, uniqueness, ordering, and recovery limit |
| --- | --- | --- |
| Session | Partial: initialization/end-related diagnostics, saved-session aggregate fields, and some time-prefixed activity are observable. Structured blocks include generic session/game settings and aggregate outcomes such as played time, score, landings, takeoffs, and fault totals. | No explicit, stable session identifier was found. A time regression and incomplete timestamps prevent reliable session splitting or reconstruction after rotation/overwrite. Treat aggregates as snapshots, not an auditable event history. |
| Aircraft | No stable individual aircraft record was established. Generic aircraft-related text occurs (641 lines), but no explicit callsign or aircraft-identifier label was found. | The generic mentions cannot be safely joined into one aircraft lifecycle, and may describe static data, diagnostics, or UI/runtime internals. No unique key is evidenced. |
| Flight | No individual flight lifecycle was established. Departure-related text occurs only sparsely (3 lines); no explicit flight-number label and no arrival label were found. | There is no evidenced identity or start/end pair with which to reconstruct a flight, retry, diversion, or completion. |
| Clearance | No canonical clearance event was established. The word `cleared` occurs in 32 lines, but an explicit clearance label was absent. | The text is insufficient to identify issuer, recipient, instruction type, acknowledgement, supersession, or outcome. It cannot safely drive a clearance state machine. |
| Runway | Partial static/reference evidence only. `runway` occurs in 340 lines and the structured data includes a `runways` field. | This confirms that runway-related information is logged somewhere, but not a dynamic runway assignment, occupancy, crossing, clearance, or release lifecycle. No reliable flight-to-runway join key is evidenced. |
| Terminal/gate | Partial static/reference evidence only. `terminal` occurs in 430 lines and `gate` in 195 lines. | These occurrences do not establish a stable terminal/gate allocation record or an aircraft association. They may belong to airport data or non-event diagnostics. |
| Failure | Partial diagnostic evidence. There are 42 lines matching `error` and 3 matching `exception`; no `fatal`, `warning`, or `crash` match was found by the same conservative scan. | Individual diagnostic lines can be retained with source order and, where available, timestamp. They have no evidenced error code, correlation ID, severity contract, recovery marker, or relation to a flight/session. |
| Restart | Not independently recoverable. No `restart` or `reload` label was found; one shutdown-related line exists. | The timestamp regression is compatible with multiple causes, including appended process histories, and is not proof of restart. It must not be used as a restart detector. |

### Counts are evidence of coverage, not event counts

**Observed.** A broad lexical scan also found 168 clearance/instruction-related lines, 340 runway-related lines, 625 terminal/gate-related lines, 281 aircraft-lifecycle-word-related lines, and 78 failure-word-related lines. Those categories overlap. They include configuration and diagnostic contexts; they are deliberately not reported as counts of aircraft, clearances, or failures.

**Inference.** The current file supports a low-risk diagnostic/log-viewer feature (sanitized text, source offset, and optional parsed timestamp), but it does not support a v1 operational model based only on inferred Player.log semantics.

## Minimal synthetic examples

These examples describe a possible TowerGlance representation. They are not copied from the game log.

```text
log_record(source_offset=1234, parsed_time=optional, category=diagnostic_error)
log_record(source_offset=1235, parsed_time=absent, category=runway_reference)
```

Neither record may be promoted to `aircraft`, `flight`, `clearance`, or `session_restart` without independently observed fields and lifecycle rules.

## Sources and evidence

- **Primary local evidence:** Tower! Simulator 3-owned `Player.log`, read-only inspection on 2026-08-02. The examined current file had 5,580 lines and was last modified the same day. Raw content and location are intentionally not published.
- **Method:** conservative structural and lexical counts; timestamp-prefix parsing; structured-key inventory; no parsing assumption was made for unlabelled prose. The count scan found no explicit callsign, flight-number, aircraft-ID, clearance, arrival, restart, or reload label.

No official public format specification was found or relied upon. This is an undocumented local interface; observed evidence, engineering inference, and future maintainer decisions remain separate.

## Uncertainties

- This is one log snapshot, not a controlled coverage corpus. Absence in this file is not proof that another TS3 version, airport, mode, logging level, or action can never emit the observation.
- Lexical matches cannot distinguish user-visible operational events from configuration, asset, engine, speech, or network diagnostics.
- The file may be appended, rotated, overwritten, or emitted differently over process starts. No lifecycle marker contract is currently evidenced.
- Any identifiers present in raw text were intentionally not counted or published as possible keys, because their meaning and privacy properties are unverified.

## Next steps

Run controlled, single-variable live scenarios and preserve only sanitized derived evidence (event category, relative order, timestamp presence, and field names/types). For each scenario, record game version, airport/mode category, and a fresh-log boundary outside the public artifact.

1. **Session boundary and restart:** fresh launch, start a session, exit to menu, start another session, quit, relaunch. Determine explicit markers, file overwrite/append behavior, timestamp reset behavior, and whether a session ID exists.
2. **Aircraft and flight identity:** create or observe one arrival and one departure through spawn, ground movement, takeoff/landing, removal, and failure. Determine a non-personal stable identifier and whether it survives the whole lifecycle.
3. **Clearance and runway lifecycle:** issue representative ground, runway, departure, arrival, and go-around instructions. Determine whether command, target, runway, acknowledgement, state change, and outcome are separately logged and ordered.
4. **Terminal/gate lifecycle:** observe assignment, arrival, release, and reassignment of a gate/terminal. Determine the join key to aircraft and flight state.
5. **Failure and recovery:** induce only safe in-game, non-destructive operational failures and observe error, recovery, retry, and restart markers. Do not infer failure semantics from an engine error alone.

Until those scenarios supply a documented, stable field and ordering contract, Player.log should be treated as diagnostic supplementary input, not the authoritative source for TowerGlance v1 live operational state.
