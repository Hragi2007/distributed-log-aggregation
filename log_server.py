#!/usr/bin/env python3
"""Centralized UDP log server (D1). Run on the server host (e.g. h_srv in Mininet).
Usage: python3 log_server.py --port 5140 --out logs
Ctrl+C prints/saves the final report."""
import socket, json, time, argparse, os, csv, signal
from collections import defaultdict

SEVS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=5140)
    ap.add_argument("--out", default="logs")
    ap.add_argument("--idle-exit", type=float, default=0,
                    help="exit after N sec of silence once a FIN was seen (0 = run until Ctrl+C)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
    sock.bind((a.bind, a.port))
    sock.settimeout(1.0)

    logf = open(os.path.join(a.out, "aggregated.log"), "a", buffering=1)
    recv = defaultdict(lambda: defaultdict(int))      # recv[host][sev]
    dsum = defaultdict(lambda: defaultdict(float))    # delay sum (s)
    dmax = defaultdict(lambda: defaultdict(float))
    sent = {}                                         # sent[host] = {sev: n} from FIN
    last_rx, got_fin, stop = time.time(), False, False

    def on_sig(*_):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGINT, on_sig)
    signal.signal(signal.SIGTERM, on_sig)
    print(f"[server] listening on {a.bind}:{a.port}")

    while not stop:
        try:
            data, addr = sock.recvfrom(65535)
        except socket.timeout:
            if a.idle_exit and got_fin and time.time() - last_rx > a.idle_exit:
                break
            continue
        now = time.time()
        last_rx = now
        try:
            m = json.loads(data.decode())
        except Exception:
            continue                                   # ignore malformed datagrams
        if m.get("type") == "FIN":
            sent[m["host"]] = m["sent"]
            got_fin = True
            continue
        h, sev = m["host"], m["sev"]
        delay = now - m["ts"]
        recv[h][sev] += 1
        dsum[h][sev] += delay
        dmax[h][sev] = max(dmax[h][sev], delay)
        logf.write(f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(m["ts"]))} '
                   f'{h} {sev} seq={m["seq"]} delay_ms={delay*1000:.2f} {m["msg"]}\n')

    rows = []
    print("\n=== REPORT ===")
    print(f'{"host":8}{"sev":10}{"sent":>7}{"recv":>7}{"loss%":>8}{"avg_ms":>9}{"max_ms":>9}')
    for h in sorted(set(recv) | set(sent)):
        for s in SEVS:
            r = recv[h][s]
            n = sent.get(h, {}).get(s)
            loss = (100.0 * (n - r) / n) if n else float("nan")
            avg = 1000 * dsum[h][s] / r if r else 0
            mx = 1000 * dmax[h][s]
            rows.append([h, s, n if n is not None else "", r, f"{loss:.2f}", f"{avg:.2f}", f"{mx:.2f}"])
            print(f'{h:8}{s:10}{str(n if n is not None else "-"):>7}{r:>7}{loss:>8.2f}{avg:>9.2f}{mx:>9.2f}')
    with open(os.path.join(a.out, "stats.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["host", "severity", "sent", "received", "loss_pct", "avg_delay_ms", "max_delay_ms"])
        w.writerows(rows)
    print(f"[server] saved {a.out}/aggregated.log and {a.out}/stats.csv")

if __name__ == "__main__":
    main()
