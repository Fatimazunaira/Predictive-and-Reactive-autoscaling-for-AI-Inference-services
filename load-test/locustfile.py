import math
import os
import random

from locust import HttpUser, LoadTestShape, constant_throughput, task

PATTERN = os.environ.get("PATTERN", "daily")      # daily | spikes | growth
DURATION = int(os.environ.get("DURATION", 600))   # seconds
PEAK = float(os.environ.get("PEAK", 150))         # max rps
BASE = float(os.environ.get("BASE", 20))          # min rps
SEED = int(os.environ.get("SEED", 42))


def build_schedule(pattern, duration, base, peak, seed):
    rng = random.Random(seed)
    if pattern == "daily":
        sched = [base + (peak - base) * (0.5 - 0.5 * math.cos(2 * math.pi * t / duration))
                 for t in range(duration)]
    elif pattern == "growth":
        sched = [base + (peak - base) * t / duration for t in range(duration)]
    elif pattern == "spikes":
        sched = [base] * duration
        n = 5
        window = duration // n
        for i in range(n):
            start = i * window + rng.randint(int(window * 0.1), int(window * 0.5))
            length = rng.randint(int(window * 0.2), int(window * 0.35))
            height = rng.uniform(0.6 * peak, peak)
            for t in range(start, min(start + length, duration)):
                sched[t] = height
    else:
        raise ValueError(f"unknown PATTERN: {pattern}")
    # +-5% noise, same every run because of the seed
    return [min(peak, max(1.0, v * (1 + rng.uniform(-0.05, 0.05)))) for v in sched]


SCHEDULE = build_schedule(PATTERN, DURATION, BASE, PEAK, SEED)


class InferenceUser(HttpUser):
    wait_time = constant_throughput(1)  # at most 1 request/s per user

    @task
    def predict(self):
        self.client.post("/predict", json={"text": "I love this product"})


class TrafficPattern(LoadTestShape):
    def tick(self):
        t = int(self.get_run_time())
        if t >= DURATION:
            return None
        return round(SCHEDULE[t]), 100  # users = target rps, fast spawn for spikes


if __name__ == "__main__":
    # preview: py -3.15 load-test\locustfile.py
    os.makedirs("results", exist_ok=True)
    with open(f"results/schedule_{PATTERN}.csv", "w") as f:
        f.write("t,target_rps\n")
        for t, v in enumerate(SCHEDULE):
            f.write(f"{t},{v:.1f}\n")
    for t in range(0, DURATION, 30):
        print(f"{t:>4}s  {SCHEDULE[t]:>6.1f} rps")