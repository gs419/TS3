"""Local pcap analyzer for the TS3 write-path capture.

Run this on the machine with the capture. It parses the loopback traffic,
auto-detects the Communication Port, extracts the client->server messages
(commands go INTO the port), and prints any that look like injected commands —
plus a small sample so we can see the exact format. The output is SMALL: paste
it back here. Nothing needs to be uploaded.

Usage:
    pip install dpkt
    python analyze_capture.py gamecapture.pcapng
    python analyze_capture.py gamecapture_split/           # a folder of split pcapngs
    python analyze_capture.py cap1.pcapng cap2.pcapng ...  # explicit list
    python analyze_capture.py gamecapture.pcapng --port 12020   # if you know it

It handles pcapng loopback captures (the format Wireshark saved). If the command
is NOT found in the port traffic, that itself is the answer: the tool injects via
keystrokes, not the port (we'd switch to the keyboard sender).
"""
import sys, os, glob, struct, re, collections
import dpkt

PORT = None
paths = []
for a in sys.argv[1:]:
    if a == "--port":
        PORT = "next"
    elif PORT == "next":
        PORT = int(a)
    elif os.path.isdir(a):
        paths += sorted(glob.glob(os.path.join(a, "*.pcapng")) +
                        glob.glob(os.path.join(a, "*.pcap")))
    else:
        paths += sorted(glob.glob(a))
if not paths:
    print("no capture files found"); sys.exit(1)

# command signatures: the ,callsign; format, ATC command verbs, or a recog
# UPDATE carrying a NON-empty recognized value. Deliberately does NOT match the
# routine CMD_REQUEST_*/CMD_RECOG_HELPER/CMD_SET_* telemetry.
SIGS = re.compile(
    r",\s*[A-Z0-9]{2,7}\s*;"                          # ,callsign; command format
    r"|\bCANCEL\b|CONTACT DEPARTURE|CLEARED (FOR|TO)|LINE UP AND WAIT"
    r"|CROSS RUNWAY|GO AROUND|PUSHBACK APPROVED|TAXI TO|FLY HEADING|CLIMB TO"
    r'|CMD_RECOG_UPDATE[^\n]*"value"\s*:\s*"[^"]',    # committed recognized speech
    re.I)

def packets(path):
    with open(path, "rb") as f:
        try:
            r = dpkt.pcapng.Reader(f)
        except Exception:
            f.seek(0); r = dpkt.pcap.Reader(f)
        for ts, buf in r:
            yield ts, buf

def ip_of(buf):
    # loopback (DLT_NULL): 4-byte family header, then IP
    for off in (4, 0):
        try:
            ip = dpkt.ip.IP(buf[off:])
            if isinstance(ip.data, dpkt.tcp.TCP):
                return ip
        except Exception:
            pass
    return None

# pass 1: find candidate loopback ports carrying JSON-ish payloads
port_bytes = collections.Counter()
for p in paths:
    for ts, buf in packets(p):
        ip = ip_of(buf)
        if not ip: continue
        t = ip.data
        if not t.data: continue
        head = t.data[:1]
        if head in (b"{", b"["):
            port_bytes[min(t.sport, t.dport)] += len(t.data)
cand = [PORT] if PORT else [p for p, _ in port_bytes.most_common(4)]
print("candidate comm ports (by JSON payload bytes):",
      dict(port_bytes.most_common(6)))
print("using ports:", cand)

# pass 2: extract client->server messages on candidate ports; flag commands
hits, sample = [], []
c2s_lines = 0
for p in paths:
    for ts, buf in packets(p):
        ip = ip_of(buf)
        if not ip: continue
        t = ip.data
        if not t.data or t.dport not in cand:   # dport in cand = INTO the port
            continue
        try:
            text = t.data.decode("utf-8", "replace")
        except Exception:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line: continue
            c2s_lines += 1
            if SIGS.search(line):
                hits.append(line[:400])
            elif len(sample) < 15:
                sample.append(line[:200])

print(f"\nclient->server lines on comm port(s): {c2s_lines}")
print(f"\n=== COMMAND-LIKE MESSAGES ({len(hits)}) ===")
for h in hits[:60]:
    print("  " + h)
if not hits:
    print("  (none found in port traffic — commands may be injected via "
          "keystrokes, not the port)")
print("\n=== sample of other client->server messages (format reference) ===")
for s in sample:
    print("  " + s)
