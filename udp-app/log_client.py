#!/usr/bin/env python3
"""UDP log client (D1). Run on each Mininet host.
Usage: python3 log_client.py --server 10.0.0.100 --name h1 --count 500 --rate 50
Critical/Error logs are marked with a DSCP value in the IP header so the SDN
controller can match them (nw_tos) and prioritize them during congestion."""
import socket, json, time, random, argparse

SEVS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
WEIGHTS = [40, 35, 15, 7, 3]
TOS = {"CRITICAL": 0xB8, "ERROR": 0x68}   # DSCP EF (46) / AF31 (26) << 2 ; others 0
SAMPLES = {
    "DEBUG": "cache lookup took 3ms", "INFO": "request served OK",
    "WARNING": "disk usage above 80%", "ERROR": "db connection failed",
    "CRITICAL": "service down, no heartbeat",
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True)
    ap.add_argument("--port", type=int, default=5140)
    ap.add_argument("--name", required=True, help="host id, e.g. h1")
    ap.add_argument("--count", type=int, default=200)
    ap.add_argument("--rate", type=float, default=20, help="msgs/sec (0 = as fast as possible)")
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    if a.seed is not None:
        random.seed(a.seed)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cur = None
    sent = {x: 0 for x in SEVS}
    gap = 1.0 / a.rate if a.rate > 0 else 0

    def set_tos(v):
        nonlocal cur
        if v != cur:
            s.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, v)
            cur = v

    for seq in range(a.count):
        sev = random.choices(SEVS, WEIGHTS)[0]
        set_tos(TOS.get(sev, 0))
        m = {"type": "LOG", "host": a.name, "seq": seq, "sev": sev,
             "ts": time.time(), "msg": SAMPLES[sev]}
        s.sendto(json.dumps(m).encode(), (a.server, a.port))
        sent[sev] += 1
        if gap:
            time.sleep(gap)

    set_tos(0xB8)                               # FIN rides the priority class
    fin = json.dumps({"type": "FIN", "host": a.name, "sent": sent}).encode()
    for _ in range(3):                          # repeated: UDP may drop it
        s.sendto(fin, (a.server, a.port))
        time.sleep(0.2)
    print(f"[{a.name}] sent {a.count} logs: {sent}")

if __name__ == "__main__":
    main()
