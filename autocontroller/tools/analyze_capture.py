"""Local capture analyzer / report for the TS3 write-path session.

Runs on the machine with the capture and prints a COMPACT report (a few KB —
paste it back). One pass harvests everything useful, not just the command:

  1. Ports        — all loopback TCP ports + payload volume + direction.
  2. Write path   — client->server command-like messages (,callsign; / verbs /
                    committed recog value). THE prize.
  3. New protocol — every distinct server->client `cmd` type + one sample, so we
                    catch any message types beyond what we've decoded.
  4. Calibration  — distinct AIRPLANES `state` ints with a sample speed/alt for
                    each (maps approach/on-final/rollout) and the airborne speed
                    range (to calibrate speed_to_mps vs known knots).
  5. Speech       — recog committed values + a few TTS SAY texts.

Usage:
    pip install dpkt
    python analyze_capture.py gamecapture.pcapng
    python analyze_capture.py gamecapture_split/         # folder of splits
    python analyze_capture.py cap.pcapng --port 12020    # if you know the port

Output goes to stdout AND capture_report.txt. Paste the report or upload that
small file. If the command is NOT in the port traffic, that's the answer too
(injection is via keystrokes -> we use the keyboard sender).
"""
import sys, os, glob, re, json, collections
import dpkt

PORT = None; paths = []
it = iter(sys.argv[1:])
for a in it:
    if a == "--port": PORT = int(next(it))
    elif os.path.isdir(a):
        paths += sorted(glob.glob(os.path.join(a, "*.pcapng")) +
                        glob.glob(os.path.join(a, "*.pcap")))
    else: paths += sorted(glob.glob(a))
if not paths: print("no capture files found"); sys.exit(1)

CMD_SIG = re.compile(
    r",\s*[A-Z0-9]{2,7}\s*;|\bCANCEL\b|CONTACT DEPARTURE|CLEARED (FOR|TO)|"
    r"LINE UP AND WAIT|CROSS RUNWAY|GO AROUND|PUSHBACK APPROVED|TAXI TO|"
    r'FLY HEADING|CLIMB TO|CMD_RECOG_UPDATE[^\n]*"value"\s*:\s*"[^"]', re.I)

def packets(path):
    with open(path, "rb") as f:
        try: r = dpkt.pcapng.Reader(f)
        except Exception: f.seek(0); r = dpkt.pcap.Reader(f)
        for ts, buf in r: yield buf

def ip_of(buf):
    for off in (4, 0):
        try:
            ip = dpkt.ip.IP(buf[off:])
            if isinstance(ip.data, dpkt.tcp.TCP): return ip
        except Exception: pass
    return None

# pass 1: find comm port(s) by JSON payload volume
vol = collections.Counter()
for p in paths:
    for buf in packets(p):
        ip = ip_of(buf)
        if ip and ip.data.data[:1] in (b"{", b"["):
            vol[min(ip.data.sport, ip.data.dport)] += len(ip.data.data)
cand = [PORT] if PORT else [p for p, _ in vol.most_common(3)]

# pass 2: harvest
cmd_hits = []
s2c_types = collections.OrderedDict()          # cmd -> (count, sample)
recog_vals, tts_says = [], []
plane_state = {}                               # state int -> (speed, alt)
air_speeds = []
def note_type(cmd, line):
    if cmd not in s2c_types: s2c_types[cmd] = [0, line[:200]]
    s2c_types[cmd][0] += 1

for p in paths:
    for buf in packets(p):
        ip = ip_of(buf);
        if not ip: continue
        t = ip.data
        if not t.data: continue
        port = min(t.sport, t.dport)
        if port not in cand: continue
        text = t.data.decode("utf-8", "replace")
        into = t.dport in cand                  # client -> server
        for line in text.splitlines():
            line = line.strip()
            if not line: continue
            if into and CMD_SIG.search(line) and len(cmd_hits) < 80:
                cmd_hits.append(line[:400])
            try: o = json.loads(line)
            except Exception: continue
            cmd = o.get("cmd") if isinstance(o.get("cmd"), str) else None
            if not into and cmd:
                note_type(cmd, line)
                if cmd == "CMD_REQUEST_AIRPLANES" and o.get("value"):
                    try:
                        for pl in json.loads(o["value"]).get("planes", []):
                            st = pl.get("state"); pos = pl.get("pos") or {}
                            spd = pl.get("spd"); alt = pos.get("y")
                            if st not in plane_state:
                                plane_state[st] = (spd, alt)
                            if (alt or 0) > 20 and spd: air_speeds.append(spd)
                    except Exception: pass
                if cmd == "SAY" and len(tts_says) < 5:
                    tts_says.append(line[:160])
            if into and cmd == "CMD_RECOG_UPDATE" and o.get("value") and len(recog_vals) < 12:
                recog_vals.append(line[:300])
            if not into and isinstance(o.get("cmd"), dict) and o["cmd"].get("type") == "SAY":
                if len(tts_says) < 5: tts_says.append(line[:160])

# report
L = []
L.append("=== TS3 CAPTURE REPORT ===")
L.append(f"files: {len(paths)}   comm port candidates (by JSON bytes): {dict(vol.most_common(4))}")
L.append(f"using ports: {cand}")
L.append(f"\n[2] WRITE PATH — command-like client->server ({len(cmd_hits)}):")
L += ["   " + h for h in cmd_hits[:80]] or ["   (none — injection likely via keystrokes, not the port)"]
L.append(f"\n[3] server->client cmd types ({len(s2c_types)}) — count : sample:")
for c, (n, s) in s2c_types.items(): L.append(f"   {c} x{n}: {s}")
L.append(f"\n[4] AIRPLANES state ints -> (speed, alt) sample:")
for st in sorted(plane_state, key=lambda x: (x is None, x)):
    L.append(f"   state {st}: spd={plane_state[st][0]} alt={plane_state[st][1]}")
if air_speeds:
    L.append(f"   airborne speed range: {min(air_speeds):.1f} .. {max(air_speeds):.1f} "
             f"(n={len(air_speeds)})  <- calibrate speed_to_mps vs known knots")
L.append(f"\n[5] recog committed values ({len(recog_vals)}):")
L += ["   " + r for r in recog_vals] or ["   (none)"]
L.append(f"\n[5b] TTS SAY samples ({len(tts_says)}):")
L += ["   " + s for s in tts_says]

report = "\n".join(L)
print(report)
open("capture_report.txt", "w", encoding="utf-8").write(report)
print("\n(also written to capture_report.txt)")
