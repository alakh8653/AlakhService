"""Queue engine: who each worker serves next, and when each waiting customer will be seen (an ETA range).

Pure and deterministic (no I/O, no clock), so the same code runs in the API, the worker, and the simulator
(tools/queue_sim.py). Times are UTC datetimes; durations are minutes.

Model
-----
One global queue per shop and day: appointments, walk-ins and VIPs together. Workers are dispatched from a
min-heap of (time the worker is next free, worker id). When a worker comes free at time t, it takes the
highest-priority customer who is ready by t and whom it may serve (skills, preferred worker, load cap). If
nobody is ready yet, the worker's next free time moves to the earliest moment someone it could serve becomes
ready. Shifts and breaks are respected: a job is not started if it would run into a break or past the
shift's end; the worker continues after the break, or is done for the day.

Priority, at time t, compares (manual rank, tier, ready time, booked time, customer key, id):
- tier: 0 VIP, 1 appointment, 2 walk-in. A walk-in who has waited aging_minutes since they were ready is
  served like an appointment (then by who was ready first), so nobody starves; aging never makes a VIP;
- a shop owner's manual reorder sets ranks, which come first, in the owner's order;
- every remaining tie is broken by booking time, then customer, then id: the order is deterministic.

Durations are learnt: each (service, worker) keeps an exponentially weighted mean and variance of actual
durations (DurationModel). A job's planned length is that mean plus the shop's buffer %. A job in progress
holds its worker until its start plus that length, and never ends earlier than a minute from now: an
overrunning job pushes everyone behind it (and is flagged).

ETA range: the start's uncertainty is the square root of the summed variances of the jobs ahead of the
customer on the same worker. The expected no-shows among those jobs (no-show rate x their lengths) pull the
likely start earlier. ETA min/max = likely start -/+ Z x sigma, never before now nor after the planned
start + Z x sigma. Confidence comes from the range's width relative to the wait.

Complexity, with M customers waiting and N workers: each dispatch pops the heap (log N) and scans the ready
customers (M), so a full recompute is O(M x (M + log N)); with M = 200 and N = 50 that is about 40,000 cheap
steps (well under 100 ms; see tests/test_queue_engine.py). Removing a customer replays only from the
dispatch step that served them (QueueEngine.remove): predictions made before that step are kept.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Dict, FrozenSet, List, Optional, Sequence, Tuple

VIP, APPOINTMENT, WALK_IN = 0, 1, 2
AVAILABLE, ON_BREAK, OFF = "AVAILABLE", "BREAK", "OFF"
WAITING, SERVING = "WAITING", "SERVING"
HIGH, MEDIUM, LOW = "HIGH", "MEDIUM", "LOW"

MIN = timedelta(minutes=1)
Span = Tuple[datetime, datetime]


@dataclass
class Config:
    buffer_pct: float = 0.10  # added to every planned duration
    z: float = 1.28  # ETA range covers about 80% of outcomes (one-sided 90%)
    aging_minutes: int = 20  # a walk-in waiting this long since ready is served like an appointment
    no_show_rate: float = 0.05  # share of booked customers who do not come
    your_turn_within: int = 2  # minutes: within this of their start, it is the customer's turn
    overrun_threshold_minutes: int = 5  # a job this far past its planned end is overrunning


@dataclass
class DurationModel:
    """Exponentially weighted mean and variance of a service's actual durations (minutes)."""

    mean: float
    var: float = 0.0
    n: int = 0

    def update(self, actual: float, alpha: float) -> "DurationModel":
        """The model after one more actual duration (West's EW variance). O(1)."""
        if self.n == 0:
            return DurationModel(actual, self.var, 1)
        diff = actual - self.mean
        mean = self.mean + alpha * diff
        var = (1 - alpha) * (self.var + alpha * diff * diff)
        return DurationModel(mean, var, self.n + 1)

    @property
    def std(self) -> float:
        return math.sqrt(max(self.var, 0.0))


@dataclass
class Worker:
    id: str
    # Services they may do; None means all of the shop's.
    skills: Optional[FrozenSet[str]] = None
    status: str = AVAILABLE
    status_until: Optional[datetime] = None  # for BREAK: when they are back
    # Today's working intervals (UTC); empty means they do not work today.
    shifts: List[Span] = field(default_factory=list)
    breaks: List[Span] = field(default_factory=list)
    # At most this many minutes of work today (None: no cap).
    load_cap_minutes: Optional[float] = None
    minutes_done: float = 0.0  # already served today (counts against the cap)

    def can_do(self, service_id: str) -> bool:
        return self.skills is None or service_id in self.skills


@dataclass
class Entry:
    id: str
    service_id: str
    tier: int  # VIP, APPOINTMENT or WALK_IN
    ready_at: datetime  # booked time, or when a walk-in (or a late customer) checked in
    booked_at: datetime
    customer_key: str = ""
    state: str = WAITING
    worker_id: Optional[str] = None  # the worker serving them (SERVING), or a provider fixed for a home visit
    started_at: Optional[datetime] = None
    preferred_worker_id: Optional[str] = None
    strict_preferred: bool = False  # only that worker, even if they are off today
    rank: Optional[float] = None  # a manual reorder by the shop
    travel_minutes: float = 0.0  # home visits: the trip before the job
    scheduled_at: Optional[datetime] = None  # the booked time, for how late it runs


@dataclass
class Prediction:
    entry_id: str
    state: str  # WAITING, YOUR_TURN, SERVING, UNSERVABLE
    position: Optional[int]  # 1 for the first customer in order; None while being served
    people_ahead: int  # customers before them in the queue's order
    ahead_on_worker: int  # jobs before theirs on the worker expected to serve them (same-skill line)
    worker_id: Optional[str]
    start: Optional[datetime]  # planned start (arrival, for a home visit)
    eta_min: Optional[datetime]
    eta_max: Optional[datetime]
    wait_min: Optional[int]
    wait_max: Optional[int]
    confidence: Optional[str]
    running_late_minutes: int = 0
    overrun: bool = False
    reason: Optional[str] = None  # NO_ELIGIBLE_WORKER, PREFERRED_UNAVAILABLE, BEYOND_SHIFT

    def bucket(self) -> Tuple:
        """What a customer would notice changing (for diffs and notifications)."""
        return (self.state, self.position, self.worker_id, self.wait_min, self.wait_max, self.reason)


Durations = Callable[[str, Optional[str]], DurationModel]


def _planned(d: DurationModel, cfg: Config) -> float:
    return max(1.0, d.mean * (1 + cfg.buffer_pct))


def _in_span(t: datetime, spans: Sequence[Span]) -> Optional[Span]:
    for s, e in spans:
        if s <= t < e:
            return (s, e)
    return None


def _fit(worker: Worker, t: datetime, minutes: float) -> Optional[datetime]:
    """The earliest start at or after [t] when [worker] can do a [minutes]-long job inside a shift and
    clear of breaks and an unfinished BREAK status; None if not today. O(shifts + breaks)."""
    if worker.status == OFF:
        return None
    if worker.status == ON_BREAK and worker.status_until and t < worker.status_until:
        t = worker.status_until
    length = timedelta(minutes=minutes)
    shifts = sorted(worker.shifts)
    for _ in range(len(shifts) + len(worker.breaks) + 2):
        shift = _in_span(t, shifts)
        if shift is None:
            later = [s for s, _ in shifts if s > t]
            if not later:
                return None
            t = min(later)
            continue
        brk = _in_span(t, worker.breaks)
        if brk:
            t = brk[1]
            continue
        end = t + length
        clash = [b for b in worker.breaks if b[0] < end and t < b[1]]
        if clash:
            t = min(b[1] for b in clash)
            continue
        if end > shift[1]:
            later = [s for s, _ in shifts if s >= shift[1]]
            if not later:
                return None
            t = min(later)
            continue
        return t
    return None


@dataclass
class _State:
    """The dispatch state after some steps, kept so a change can replay from that step."""

    heap: List[Tuple[datetime, str]]
    free_at: Dict[str, datetime]
    var_on: Dict[str, float]  # summed duration variance of the jobs planned on each worker
    queued_on: Dict[str, List[Tuple[str, float]]]  # waiting jobs planned on each worker: (entry id, minutes)
    done_minutes: Dict[str, float]
    remaining: List[str]  # waiting entry ids not yet dispatched


class QueueEngine:
    """Predicts one shop's day; keeps its dispatch steps so a removal replays only from where it mattered."""

    def __init__(self, cfg: Config, durations: Durations):
        self.cfg = cfg
        self.durations = durations
        self.now: Optional[datetime] = None
        self.workers: Dict[str, Worker] = {}
        self.entries: Dict[str, Entry] = {}
        self.predictions: Dict[str, Prediction] = {}
        self._steps: List[Tuple[str, _State]] = []  # (entry dispatched at this step, state before it)
        self._initial: Optional[_State] = None

    # ------------------------------------------------------------------ public API

    def predict(self, now: datetime, workers: Sequence[Worker], entries: Sequence[Entry]) -> Dict[str, Prediction]:
        """Every customer's prediction for the shop's day. O(M x (M + log N))."""
        self.now = now
        self.workers = {w.id: w for w in workers}
        self.entries = {e.id: e for e in entries}
        self.predictions = {}
        self._steps = []
        state = self._start_state()
        self._initial = self._copy(state)
        self._run(state)
        self._number()
        return self.predictions

    def remove(self, entry_id: str) -> Dict[str, Prediction]:
        """Drops a customer (cancelled, no-show, done) and replays only the dispatch steps from theirs on.
        Returns the predictions that changed (the diff). O((M - k) x (M + log N)) for removal at step k."""
        if entry_id not in self.entries or self.now is None:
            return {}
        before = dict(self.predictions)
        entry = self.entries.pop(entry_id)
        self.predictions.pop(entry_id, None)
        if entry.state == SERVING:  # frees a worker now: everything downstream may move
            return self._diff(before, self.predict(self.now, list(self.workers.values()), list(self.entries.values())))
        index = next((i for i, (eid, _) in enumerate(self._steps) if eid == entry_id), None)
        if index is None:  # never dispatched (unservable): nothing else moves
            return self._diff(before, self.predictions)
        state = self._copy(self._steps[index][1])
        state.remaining = [e for e in state.remaining if e in self.entries]  # also those removed before
        for eid, _ in self._steps[index + 1 :]:
            self.predictions.pop(eid, None)
        self._steps = self._steps[:index]
        self._run(state)
        self._number()
        return self._diff(before, self.predictions)

    # ------------------------------------------------------------------ dispatch

    def _start_state(self) -> _State:
        now, cfg = self.now, self.cfg
        free_at: Dict[str, datetime] = {}
        var_on: Dict[str, float] = {w: 0.0 for w in self.workers}
        done: Dict[str, float] = {w.id: w.minutes_done for w in self.workers.values()}
        for e in sorted((e for e in self.entries.values() if e.state == SERVING), key=lambda e: e.id):
            w = e.worker_id
            d = self.durations(e.service_id, w)
            started = e.started_at or now
            planned_end = started + timedelta(minutes=_planned(d, cfg))
            end = max(planned_end, now + MIN)
            overrun = now > planned_end + timedelta(minutes=cfg.overrun_threshold_minutes)
            if w in self.workers:
                free_at[w] = max(free_at.get(w, now), end)
                var_on[w] = var_on.get(w, 0.0) + (d.var if not overrun else 0.0)
                done[w] = done.get(w, 0.0) + _planned(d, cfg)
            self.predictions[e.id] = Prediction(
                e.id, SERVING, None, 0, 0, w, started, started, end, 0, 0, HIGH, overrun=overrun
            )
        heap = []
        for w in sorted(self.workers.values(), key=lambda w: w.id):
            if w.status == OFF or not w.shifts:
                continue
            t = max(now, free_at.get(w.id, now))
            heap.append((t, w.id))
            free_at[w.id] = t
        heapq.heapify(heap)
        waiting = [e.id for e in self.entries.values() if e.state == WAITING]
        return _State(heap, free_at, var_on, {w: [] for w in self.workers}, done, waiting)

    def _key(self, e: Entry, t: datetime) -> Tuple:
        tier = e.tier
        if tier == WALK_IN and (t - e.ready_at) >= timedelta(minutes=self.cfg.aging_minutes):
            tier = APPOINTMENT  # aging: waited long enough to go with the appointments (never ahead of VIPs)
        rank = e.rank if e.rank is not None else math.inf
        return (rank, tier, e.ready_at, e.booked_at, e.customer_key, e.id)

    def _eligible(self, e: Entry, w: Worker) -> bool:
        if not w.can_do(e.service_id):
            return False
        if e.worker_id and e.worker_id != w.id:  # a home visit given to a provider
            return False
        pref = e.preferred_worker_id
        if pref and pref != w.id:
            preferred = self.workers.get(pref)
            # Keep to the preferred worker while they work today; otherwise anyone (unless strict).
            if e.strict_preferred or (preferred and preferred.status != OFF and preferred.shifts):
                return False
        return True

    def _minutes(self, e: Entry, w: Worker) -> float:
        return _planned(self.durations(e.service_id, w.id), self.cfg) + e.travel_minutes

    def _run(self, state: _State) -> None:
        cfg, now = self.cfg, self.now
        guard = 0
        while state.remaining and state.heap and guard < 10 * (len(self.entries) + len(self.workers)) + 100:
            guard += 1
            t, wid = heapq.heappop(state.heap)
            w = self.workers[wid]
            candidates = [self.entries[eid] for eid in state.remaining if self._eligible(self.entries[eid], w)]
            if not candidates:
                continue  # nobody left this worker may serve: they are done for the day
            if w.load_cap_minutes is not None and state.done_minutes.get(wid, 0.0) >= w.load_cap_minutes:
                continue
            ready = [e for e in candidates if e.ready_at <= t]
            if not ready:  # wait for the next one this worker could serve
                heapq.heappush(state.heap, (min(e.ready_at for e in candidates), wid))
                continue
            # The best one whose job fits in the worker's day (a shorter one may fit before closing).
            ordered = sorted(ready, key=lambda e: self._key(e, t))
            # If another worker free now can take the first one, take someone only this worker may serve
            # (e.g. who asked for them), so nobody waits while a worker stands idle. O(N x M).
            free = [self.workers[x] for tt, x in state.heap if tt <= t]
            if free and len(ordered) > 1 and any(self._eligible(ordered[0], o) for o in free):
                only = next((e for e in ordered if not any(self._eligible(e, o) for o in free)), None)
                if only is not None:
                    ordered.remove(only)
                    ordered.insert(0, only)
            chosen, start = None, None
            for e in ordered:
                start = _fit(w, t, self._minutes(e, w))
                if start is not None:
                    chosen = e
                    break
            if chosen is None:
                continue  # no room left in this worker's day
            if start > t:  # a break or the next shift: come back then
                heapq.heappush(state.heap, (start, wid))
                continue
            minutes = self._minutes(chosen, w)
            snapshot = self._copy(state)
            heapq.heappush(snapshot.heap, (t, wid))  # the state just before this worker was popped
            self._steps.append((chosen.id, snapshot))
            state.remaining.remove(chosen.id)
            d = self.durations(chosen.service_id, wid)
            sigma = math.sqrt(state.var_on.get(wid, 0.0))
            if start <= max(now, chosen.ready_at) and not state.queued_on.get(wid):
                sigma = min(sigma, 1.0)  # an idle worker waits for them: little doubt
            ahead = state.queued_on.setdefault(wid, [])
            no_show_shift = cfg.no_show_rate * sum(m for _, m in ahead)
            likely = max(now, start - timedelta(minutes=no_show_shift))
            spread = timedelta(minutes=cfg.z * sigma)
            eta_min = max(now, likely - spread)
            eta_max = max(eta_min, start + spread)
            wait_min = int((eta_min - now).total_seconds() // 60)
            wait_max = int(math.ceil((eta_max - now).total_seconds() / 60))
            width = wait_max - wait_min
            confidence = (
                HIGH if width <= max(5, 0.25 * wait_max) else MEDIUM if width <= max(10, 0.5 * wait_max) else LOW
            )
            late = 0
            if chosen.scheduled_at:
                late = max(0, int((start - chosen.scheduled_at).total_seconds() // 60))
            st = "YOUR_TURN" if start - now <= timedelta(minutes=cfg.your_turn_within) else WAITING
            self.predictions[chosen.id] = Prediction(
                chosen.id,
                st,
                None,
                0,
                len(ahead),
                wid,
                start,
                eta_min,
                eta_max,
                wait_min,
                wait_max,
                confidence,
                running_late_minutes=late,
                reason=(
                    "PREFERRED_UNAVAILABLE"
                    if chosen.preferred_worker_id and chosen.preferred_worker_id != wid
                    else None
                ),
            )
            ahead.append((chosen.id, minutes))
            state.var_on[wid] = state.var_on.get(wid, 0.0) + d.var
            state.done_minutes[wid] = state.done_minutes.get(wid, 0.0) + minutes
            state.free_at[wid] = start + timedelta(minutes=minutes)
            heapq.heappush(state.heap, (state.free_at[wid], wid))
        for eid in state.remaining:  # nobody can serve them today
            e = self.entries[eid]
            able = [w for w in self.workers.values() if w.can_do(e.service_id) and w.status != OFF and w.shifts]
            reason = "NO_ELIGIBLE_WORKER" if not able else "BEYOND_SHIFT"
            self.predictions[eid] = Prediction(
                eid, "UNSERVABLE", None, 0, 0, None, None, None, None, None, None, None, reason=reason
            )

    def _number(self) -> None:
        """Positions in the queue's order: by planned start, then the priority key. O(M log M)."""
        waiting = [p for p in self.predictions.values() if p.state in (WAITING, "YOUR_TURN")]
        waiting.sort(key=lambda p: (p.start, self._key(self.entries[p.entry_id], self.now)))
        for i, p in enumerate(waiting):
            p.position = i + 1
            p.people_ahead = i

    @staticmethod
    def _copy(s: _State) -> _State:
        return _State(
            list(s.heap),
            dict(s.free_at),
            dict(s.var_on),
            {k: list(v) for k, v in s.queued_on.items()},
            dict(s.done_minutes),
            list(s.remaining),
        )

    @staticmethod
    def _diff(before: Dict[str, Prediction], after: Dict[str, Prediction]) -> Dict[str, Prediction]:
        return {k: v for k, v in after.items() if k not in before or before[k].bucket() != v.bucket()}


def predict(
    now: datetime, workers: Sequence[Worker], entries: Sequence[Entry], cfg: Config, durations: Durations
) -> Dict[str, Prediction]:
    """One-shot prediction (see QueueEngine.predict)."""
    return QueueEngine(cfg, durations).predict(now, workers, entries)


def diff(before: Dict[str, Prediction], after: Dict[str, Prediction]) -> Dict[str, Prediction]:
    """Predictions that changed in a way a customer would notice (new, moved, re-estimated). O(M)."""
    return QueueEngine._diff(before, after)


__all__ = [
    "AVAILABLE",
    "APPOINTMENT",
    "Config",
    "DurationModel",
    "Entry",
    "OFF",
    "ON_BREAK",
    "Prediction",
    "QueueEngine",
    "SERVING",
    "VIP",
    "WAITING",
    "WALK_IN",
    "Worker",
    "diff",
    "predict",
]
