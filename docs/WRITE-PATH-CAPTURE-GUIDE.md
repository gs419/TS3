# Capture guide: confirming the command WRITE path

Everything in this repo can already *read* the sim and *decide* correctly. The
one missing piece to make the AI controllers **act** is the exact message that
injects a command into the game. This guide is how to capture it. One good
20-minute session gives us all three open items at once.

## What we're capturing (and why)

1. **The committed-command message (the write path).** The recog module streams
   `CMD_RECOG_UPDATE` to the game; in the earlier capture every one had an empty
   `value` (no voice command was committed). We need one capture where you
   actually issue a spoken command, so we can see the exact message that carries
   a *recognized, committed* command — then an external client can send the same
   shape to issue commands. Backup signals in the same capture: the game's
   `Real commands:` / `COMMAND:` log lines confirm what it accepted.
2. **Airborne arrival states (for compression + on-final).** The pcap we have
   was all ground traffic, so the `AIRPLANES` `state` ints for approach / on
   final / landing are still unknown. Watching one arrival from final to
   touchdown reveals them.
3. **A go-around (optional bonus)** for the revector work.

## Setup (once)

- **Find the Communication Port:** TS3 Settings → the "Communication Port"
  value (was 12020 in the last capture; it's selectable, so note the current
  one). Call it `PORT`.
- **Capture tool:** Wireshark with the **npcap loopback** adapter (install
  npcap with "loopback support" if needed). Or reuse whatever produced
  `TS32.pcapng` before — that worked perfectly.
- **Log:** you'll also grab `Player.log` (and `Player-prev.log`) from
  `%AppData%\..\LocalLow\FeelThere_*\Tower! Simulator 3\` right after.

## Capture steps

1. Start Wireshark on the loopback adapter with capture filter:
   `tcp port PORT` (substitute the number). Start capturing.
2. Launch TS3, start a **single-player** session at any airport (KBUR/KCLE
   fine). Let it load fully.
3. **Departure command:** pick a departure, press push-to-talk (right-Ctrl by
   default) and speak one clear command, e.g.
   *"November one two three, runway two five, cleared for takeoff."*
   Watch for the game to read it back (that means it committed).
4. **Arrival command + states:** take one arrival on final; speak
   *"<callsign>, runway two five, cleared to land."* Let it land. If you can,
   watch a second arrival from a few miles out through touchdown.
5. **(Optional) go-around:** send one arrival around
   (*"<callsign>, go around."*).
6. Note wall-clock times of each spoken command (helps me line up packets).
7. Stop the capture. Save as `TS3-write.pcapng`. Copy `Player.log` and
   `Player-prev.log`.

Keep it short — a handful of commands is plenty; a smaller file is easier.

## What to send back

- `TS3-write.pcapng`
- `Player.log` and `Player-prev.log` from the same session
- the `PORT` number and rough timestamps of the commands you spoke

## What I'll extract

- The recog→game message that carries the committed command (its `cmd`, flags,
  and `value` shape) → wire `senders.TcpProbeSender` to emit it, closing the
  write path so the arrival/departure/ground/multi-position controllers can
  actually issue commands instead of dry-running.
- The `AIRPLANES` `state` ints for approach / on-final / flare / rollout →
  tighten `worldmodel._airborne()` and the compression/on-final triggers.
- If a go-around is included, the state transition for revector timing.

## Safety

Loopback only, and **capture passively** — don't send anything to `PORT` yet.
An earlier community effort saw the game crash around active instrumentation, so
we confirm the read/observe path first and only then test a single injected
command on a throwaway session. Keep a save you don't mind losing for the first
write test.

## After this
With the committed-command shape known, the remaining work is wiring, not
discovery: point the senders at it, gate it behind a per-position enable, and
start on an easy field (KBUR, one runway) in copilot mode before letting the
full multi-position system run.
