"""Discrete-event simulator for the queue engine: how accurate are the waits customers are shown?

A shop day is simulated event by event (arrivals, finishes, breaks, no-shows). Workers follow the engine's
own plan: when one is free, they start whoever the engine planned to start with them now. Durations are
random (lognormal around each worker's true pace, which the shop does not know at first), so plans slip;
the engine learns the paces from finished visits (exponential averages) as a real shop's would.

For every customer, the start the engine predicts when they arrive (the wait shown on joining) is compared
with when they actually start. Reported: MAE, P90 and worst absolute error, the share within 5 and 10
minutes, and how often the actual start falls inside the shown range (eta_min..eta_max).

  python tools/queue_sim.py                      # the default shop, 1,000 days
  python tools/queue_sim.py --days 200 --sweep   # also tune alpha and the buffer
  python tools/queue_sim.py --edge               # N=1, a 3x spike, all on break, an overrun cascade

Pure Python and seeded, so a run is repeatable.
"""

import argparse
import heapq
import math
import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import queue_engine as qe  # noqa: E402

DAY0 = datetime(2030, 1, 1, 4, 30, tzinfo=timezone.utc)  # 10:00 in India
OPEN_MINUTES = 600  # 10:00 to 20:00


@dataclass
class Scenario:
    name: str = "default"
    workers: int = 3
    # service: (nominal minutes, share of visits, workers who do it (None: everyone))
    services: Dict[str, Tuple[float, float, Optional[Tuple[int, ...]]]] = field(
        default_factory=lambda: {
            "cut": (30, 0.55, None),
            "beard": (15, 0.25, None),
            "colour": (60, 0.20, (0, 1)),
        }
    )
    walk_ins_per_hour: float = 3.0
    appointments_per_day: int = 18
    no_show_rate: float = 0.08
    late_sd_minutes: float = 6.0  # appointment arrival around the booked time
    duration_sigma: float = 0.2  # lognormal spread of one visit's length
    pace_spread: float = 0.15  # each worker's true pace vs the nominal (unknown to the shop at first)
    overrun_rate: float = 0.0  # share of visits that take twice as long
    spike: Optional[Tuple[int, int, float]] = None  # (from minute, to minute, x walk-in rate)
    breaks: bool = True  # each worker takes 30 minutes between 13:00 and 15:00
    all_break_at: Optional[int] = None  # everyone on a 30-minute break from this minute
    grace_minutes: int = 10


@dataclass
class Result:
    errors: List[float] = field(default_factory=list)  # actual start - predicted start, minutes
    in_range: int = 0
    waits: List[float] = field(default_factory=list)
    served: int = 0
    no_shows: int = 0
    unserved: int = 0
    worst: Tuple[float, str] = (0.0, "")

    def merge(self, other: "Result") -> None:
        self.errors += other.errors
        self.in_range += other.in_range
        self.waits += other.waits
        self.served += other.served
        self.no_shows += other.no_shows
        self.unserved += other.unserved
        if abs(other.worst[0]) > abs(self.worst[0]):
            self.worst = other.worst

    def summary(self) -> dict:
        absolute = sorted(abs(e) for e in self.errors)
        n = len(absolute) or 1
        return {
            "customers": len(self.errors),
            "mae_min": round(sum(absolute) / n, 2),
            "p90_min": round(absolute[int(0.9 * (len(absolute) - 1))] if absolute else 0.0, 2),
            "worst_min": round(self.worst[0], 1),
            "within_5_min": round(sum(1 for e in absolute if e <= 5) / n, 3),
            "within_10_min": round(sum(1 for e in absolute if e <= 10) / n, 3),
            "in_shown_range": round(self.in_range / n, 3),
            "bias_min": round(statistics.mean(self.errors), 2) if self.errors else 0.0,
            "avg_wait_min": round(statistics.mean(self.waits), 1) if self.waits else 0.0,
            "served": self.served,
            "no_shows": self.no_shows,
            "unserved": self.unserved,
        }


def _at(minutes: float) -> datetime:
    return DAY0 + timedelta(minutes=minutes)


def _minutes(at: datetime) -> float:
    return (at - DAY0).total_seconds() / 60


class Day:
    def __init__(self, sc: Scenario, cfg: qe.Config, alpha: float, models: dict, paces: dict, rnd: random.Random):
        self.sc, self.cfg, self.alpha, self.models, self.paces, self.rnd = sc, cfg, alpha, models, paces, rnd
        self.result = Result()
        self.workers: List[qe.Worker] = []
        for i in range(sc.workers):
            skills = frozenset(s for s, (_, _, who) in sc.services.items() if who is None or i in who)
            breaks = []
            if sc.breaks:
                start = rnd.uniform(180, 300)
                breaks.append((_at(start), _at(start + 30)))
            if sc.all_break_at is not None:
                breaks.append((_at(sc.all_break_at), _at(sc.all_break_at + 30)))
            self.workers.append(qe.Worker(f"w{i}", skills, shifts=[(_at(0), _at(OPEN_MINUTES + 120))], breaks=breaks))
        self.entries: Dict[str, qe.Entry] = {}
        self.present: Dict[str, bool] = {}
        self.predicted: Dict[str, Tuple[float, float, float]] = {}  # id -> (start, eta_min, eta_max) on arrival
        self.arrived_at: Dict[str, float] = {}
        self.busy: Dict[str, Tuple[float, str]] = {}  # worker -> (finish minute, entry id)
        self.events: List[Tuple[float, int, str, str]] = []  # (minute, order, kind, id)
        self._n = 0

    def push(self, minute: float, kind: str, ref: str) -> None:
        self._n += 1
        heapq.heappush(self.events, (minute, self._n, kind, ref))

    def service(self) -> str:
        r, acc = self.rnd.random(), 0.0
        for name, (_, share, _) in self.sc.services.items():
            acc += share
            if r <= acc:
                return name
        return next(iter(self.sc.services))

    def durations(self, service_id: str, worker_id: Optional[str]) -> qe.DurationModel:
        model = self.models.get((service_id, worker_id or ""))
        if model and model.n >= 3:
            return model
        nominal = self.sc.services[service_id][0]
        return self.models.get((service_id, "")) or qe.DurationModel(nominal, (0.2 * nominal) ** 2, 0)

    def plan(self, minute: float) -> Dict[str, qe.Prediction]:
        now = _at(minute)
        entries = []
        for e in self.entries.values():
            if e.state == qe.WAITING and not self.present[e.id] and e.ready_at <= now:
                # Booked, due, not here yet: expected any moment (until the grace period ends).
                entries.append(qe.Entry(**{**e.__dict__, "ready_at": now + timedelta(minutes=1)}))
            else:
                entries.append(e)
        return qe.predict(now, self.workers, entries, self.cfg, self.durations)

    def run(self) -> Result:
        sc, rnd = self.sc, self.rnd
        # Appointments, booked earlier in the day's slots; some never come, the rest a little early or late.
        for i in range(sc.appointments_per_day):
            booked = rnd.randrange(0, OPEN_MINUTES - 60, 15)
            eid = f"a{i}"
            self.entries[eid] = qe.Entry(eid, self.service(), qe.APPOINTMENT, _at(booked), _at(-1000 + i), eid)
            self.entries[eid].scheduled_at = _at(booked)
            self.present[eid] = False
            if rnd.random() < sc.no_show_rate:
                self.push(booked + sc.grace_minutes, "no_show", eid)
            else:
                self.push(max(-10.0, booked + rnd.gauss(0, sc.late_sd_minutes)), "arrive", eid)
        # Walk-ins: a Poisson process (thinned for a spike).
        peak = max(1.0, sc.spike[2] if sc.spike else 1.0)
        t, i = 0.0, 0
        while True:
            t += rnd.expovariate(sc.walk_ins_per_hour * peak / 60)
            if t >= OPEN_MINUTES - 30:
                break
            rate = sc.walk_ins_per_hour * (sc.spike[2] if sc.spike and sc.spike[0] <= t < sc.spike[1] else 1.0)
            if rnd.random() < rate / (sc.walk_ins_per_hour * peak):
                self.push(t, "walk_in", f"w{i}")
                i += 1
        for w in self.workers:  # a worker back from a break looks for the next customer
            for _, end in w.breaks:
                self.push(_minutes(end), "check", w.id)
        self.push(0, "check", "")
        while self.events:
            minute, _, kind, ref = heapq.heappop(self.events)
            if kind == "walk_in":
                self.entries[ref] = qe.Entry(ref, self.service(), qe.WALK_IN, _at(minute), _at(minute), ref)
                self.present[ref] = True
                self._joined(ref, minute)
            elif kind == "arrive":
                self.present[ref] = True
                self.entries[ref].ready_at = max(self.entries[ref].scheduled_at, _at(minute))
                self._joined(ref, minute)
            elif kind == "no_show":
                e = self.entries.get(ref)
                if e is not None and e.state == qe.WAITING and not self.present[ref]:
                    del self.entries[ref]
                    self.result.no_shows += 1
            elif kind == "finish":
                wid = ref
                _, eid = self.busy.pop(wid)
                e = self.entries.pop(eid)
                actual = minute - _minutes(e.started_at)
                for key in ((e.service_id, wid), (e.service_id, "")):
                    base = self.models.get(key) or qe.DurationModel(self.sc.services[e.service_id][0], 0.0, 0)
                    self.models[key] = base.update(actual, self.alpha)
            self._dispatch(minute)
        self.result.unserved += sum(1 for e in self.entries.values() if self.present.get(e.id))
        return self.result

    def _joined(self, eid: str, minute: float) -> None:
        self.arrived_at[eid] = minute
        p = self.plan(minute).get(eid)
        if p is not None and p.start is not None:
            self.predicted[eid] = (_minutes(p.start), _minutes(p.eta_min), _minutes(p.eta_max))

    def _dispatch(self, minute: float) -> None:
        free = [w for w in self.workers if w.id not in self.busy]
        if not free or not any(e.state == qe.WAITING and self.present[e.id] for e in self.entries.values()):
            return
        plan = self.plan(minute)
        for w in free:
            starting = [
                p for p in plan.values()
                if p.worker_id == w.id and p.start is not None and _minutes(p.start) <= minute + 1e-6
                and self.entries[p.entry_id].state == qe.WAITING and self.present[p.entry_id]
            ]  # fmt: skip
            if not starting:
                upcoming = [_minutes(p.start) for p in plan.values() if p.worker_id == w.id and p.start is not None]
                if upcoming and min(upcoming) > minute:
                    self.push(min(upcoming), "check", w.id)
                continue
            p = min(starting, key=lambda p: p.start)
            e = self.entries[p.entry_id]
            e.state, e.worker_id, e.started_at = qe.SERVING, w.id, _at(minute)
            nominal = self.sc.services[e.service_id][0]
            length = nominal * self.paces[(e.service_id, w.id)] * math.exp(self.rnd.gauss(0, self.sc.duration_sigma))
            if self.rnd.random() < self.sc.overrun_rate:
                length *= 2
            self.busy[w.id] = (minute + length, e.id)
            self.push(minute + length, "finish", w.id)
            self._started(e.id, minute)
            plan = self.plan(minute)  # the next free worker plans without this customer

    def _started(self, eid: str, minute: float) -> None:
        self.result.served += 1
        self.result.waits.append(minute - self.arrived_at.get(eid, minute))
        if eid not in self.predicted:
            return
        start, low, high = self.predicted[eid]
        error = minute - start
        self.result.errors.append(error)
        if low - 0.5 <= minute <= high + 0.5:
            self.result.in_range += 1
        if abs(error) > abs(self.result.worst[0]):
            self.result.worst = (error, eid)


def simulate(sc: Scenario, days: int, alpha: float = 0.2, buffer_pct: float = 0.0, seed: int = 7) -> Result:
    """[days] consecutive days at one shop; the learnt paces carry over from day to day."""
    rnd = random.Random(seed)
    paces = {
        (s, f"w{i}"): rnd.uniform(1 - sc.pace_spread, 1 + sc.pace_spread)
        for s in sc.services
        for i in range(sc.workers)
    }
    cfg = qe.Config(buffer_pct=buffer_pct, aging_minutes=20, no_show_rate=sc.no_show_rate * 0.5)
    models: dict = {}
    total = Result()
    for _ in range(days):
        total.merge(Day(sc, cfg, alpha, models, paces, rnd).run())
    return total


EDGE = {
    "one worker": Scenario("one worker", workers=1, walk_ins_per_hour=1.2, appointments_per_day=8),
    "3x spike 12:00-14:00": Scenario("3x spike", spike=(120, 240, 3.0)),
    "empty shop": Scenario("empty", walk_ins_per_hour=0.2, appointments_per_day=2),
    "everyone on break 15:00": Scenario("all on break", all_break_at=300),
    "overrun cascade (10% take 2x)": Scenario("overruns", overrun_rate=0.10),
}


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--days", type=int, default=1000)
    parser.add_argument("--alpha", type=float, default=0.2)
    parser.add_argument("--buffer", type=float, default=0.0)
    parser.add_argument("--sweep", action="store_true", help="try alpha and buffer values")
    parser.add_argument("--edge", action="store_true", help="also run the edge cases")
    args = parser.parse_args(argv)

    began = time.perf_counter()
    base = simulate(Scenario(), args.days, args.alpha, args.buffer)
    print(f"Default shop, {args.days} days (alpha {args.alpha}, buffer {args.buffer:.0%}):")
    for k, v in base.summary().items():
        print(f"  {k:16} {v}")
    if args.sweep:
        print("\nTuning (MAE / P90 / in shown range):")
        for alpha in (0.1, 0.2, 0.3, 0.5):
            for buffer in (0.0, 0.05, 0.10):
                s = simulate(Scenario(), max(50, args.days // 5), alpha, buffer).summary()
                print(
                    f"  alpha {alpha:<4} buffer {buffer:<5.0%} {s['mae_min']:6} {s['p90_min']:6} {s['in_shown_range']:6}"
                )
    if args.edge:
        print("\nEdge cases (60 days each):")
        for name, sc in EDGE.items():
            s = simulate(sc, 60, args.alpha, args.buffer).summary()
            print(
                f"  {name:30} MAE {s['mae_min']:5}  P90 {s['p90_min']:5}  worst {s['worst_min']:6}  "
                f"in range {s['in_shown_range']:5}  wait {s['avg_wait_min']:5}  unserved {s['unserved']}"
            )
    print(f"\n({time.perf_counter() - began:.1f} s)")


if __name__ == "__main__":
    main()
