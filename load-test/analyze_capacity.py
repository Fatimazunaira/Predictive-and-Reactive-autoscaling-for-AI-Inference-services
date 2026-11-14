import csv
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "results/capacity_stats_history.csv"
target_ms = 300

last_row = {}
with open(path, newline="") as f:
    for row in csv.DictReader(f):
        if row["Requests/s"] in ("", "N/A") or row["95%"] in ("", "N/A"):
            continue
        last_row[int(row["User Count"])] = row  # keeps the last row of each step

print(f"{'users':>6} {'rps':>8} {'p95 ms':>8} {'fail/s':>8}")
capacity = None
for users in sorted(last_row):
    r = last_row[users]
    rps, p95, fails = float(r["Requests/s"]), float(r["95%"]), float(r["Failures/s"])
    print(f"{users:>6} {rps:>8.1f} {p95:>8.0f} {fails:>8.1f}")
    if p95 <= target_ms and fails == 0:
        capacity = rps

print()
print(f"Capacity (highest rps with p95 <= {target_ms} ms and no failures): {capacity}")