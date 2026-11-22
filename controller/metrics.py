"""Metrics collector: Nginx access log + Docker state -> one CSV row per window.

Run:     py -3.15 controller\\metrics.py --out results\\metrics.csv
Import:  from metrics import Collector   (scalers call Collector().snapshot(...))
"""
import argparse
import collections
import csv
import math
import os
import threading
import time

import docker

SLOW_MS = 300
INTERVAL_S = 5
LAG_S = 1.0  # read windows slightly in the past so late log lines are included
FIELDS = ["epoch", "t_s", "requests", "rps", "p50_ms", "p95_ms", "mean_ms",
          "errors", "slow", "replicas_running", "replicas_serving"]


def percentile(values, p):
    if not values:
        return None
    s = sorted(values)
    return s[max(0, math.ceil(p / 100 * len(s)) - 1)]


class Collector:
    def __init__(self):
        self.client = docker.from_env()
        found = self.client.containers.list(
            filters={"label": "com.docker.compose.service=nginx"})
        if not found:
            raise SystemExit("Nginx container not found. Start it with: "
                             "docker compose up -d --scale model=1")
        self.nginx = found[0]
        self.events = collections.deque()  # (host_time, status, latency_ms, upstream)
        self.lock = threading.Lock()
        threading.Thread(target=self._follow, daemon=True).start()

    def _follow(self):
        buf = b""
        for chunk in self.nginx.logs(stream=True, follow=True, tail=0):
            buf += chunk
            *lines, buf = buf.split(b"\n")
            now = time.time()
            for raw in lines:
                parts = raw.decode("utf-8", "ignore").split(None, 2)
                try:
                    status, latency = int(parts[0]), float(parts[1]) * 1000
                except (ValueError, IndexError):
                    continue  # not an access-log line
                upstream = parts[2].split(",")[-1].strip() if len(parts) == 3 else "-"
                with self.lock:
                    self.events.append((now, status, latency, upstream))

    def replicas_running(self):
        return len(self.client.containers.list(filters={
            "label": "com.docker.compose.service=model", "status": "running"}))

    def snapshot(self, end=None, interval=INTERVAL_S):
        """Metrics for the window [end - interval, end)."""
        end = end or (time.time() - LAG_S)
        start = end - interval
        with self.lock:
            while self.events and self.events[0][0] < start - 30:
                self.events.popleft()
            sel = [e for e in self.events if start <= e[0] < end]
        lat = [e[2] for e in sel]
        return {
            "epoch": round(end, 1),
            "requests": len(sel),
            "rps": round(len(sel) / interval, 1),
            "p50_ms": None if not lat else round(percentile(lat, 50)),
            "p95_ms": None if not lat else round(percentile(lat, 95)),
            "mean_ms": None if not lat else round(sum(lat) / len(lat)),
            "errors": sum(1 for e in sel if e[1] >= 500),
            "slow": sum(1 for x in lat if x > SLOW_MS),
            "replicas_running": self.replicas_running(),
            "replicas_serving": len({e[3] for e in sel if e[1] < 500}),
            "lat": lat,
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/metrics.csv")
    ap.add_argument("--interval", type=float, default=INTERVAL_S)
    ap.add_argument("--duration", type=float, default=0, help="seconds; 0 = until Ctrl+C")
    a = ap.parse_args()

    if os.path.exists(a.out):
        raise SystemExit(f"{a.out} already exists. Choose a new name (no overwriting).")
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)

    c = Collector()
    t0 = time.time()
    tick = t0 + a.interval
    all_lat, total_err = [], 0
    print(f"Collecting every {a.interval:g}s into {a.out}. Ctrl+C to stop.")

    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        try:
            while True:
                time.sleep(max(0, tick - time.time()))
                row = c.snapshot(end=tick - LAG_S, interval=a.interval)
                row["t_s"] = round(tick - t0, 1)
                w.writerow(row)
                f.flush()
                all_lat += row["lat"]
                total_err += row["errors"]
                print(f"{row['t_s']:6.0f}s  rps={row['rps']:6.1f}  p95={row['p95_ms'] or '-':>5}ms  "
                      f"err={row['errors']}  running={row['replicas_running']}  "
                      f"serving={row['replicas_serving']}")
                tick += a.interval
                if a.duration and tick - t0 > a.duration:
                    break
        except KeyboardInterrupt:
            pass

    print(f"\nTotal requests: {len(all_lat)}  errors: {total_err}  "
          f"overall p95: {round(percentile(all_lat, 95) or 0)} ms")


if __name__ == "__main__":
    main()