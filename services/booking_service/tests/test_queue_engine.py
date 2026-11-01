"""The queue engine: dispatch order, skills, shifts and breaks, ETA ranges, learnt durations, incremental removal."""

import random
import time
from datetime import datetime, timedelta, timezone

from app.core.queue_engine import (
    APPOINTMENT,
    OFF,
    ON_BREAK,
    SERVING,
    VIP,
    WALK_IN,
    Config,
    DurationModel,
    Entry,
    QueueEngine,
    Worker,
    predict,
)

T = datetime(2030, 11, 4, 4, 30, tzinfo=timezone.utc)
MIN = timedelta(minutes=1)
DAY = [(T - 2 * 60 * MIN, T + 10 * 60 * MIN)]  # a long shift around T
CFG = Config(buffer_pct=0.0, no_show_rate=0.0, aging_minutes=10_000)


def durations(minutes=30, var=0.0, by_service=None):
    by_service = by_service or {}

    def look(service_id, worker_id):
        return DurationModel(by_service.get(service_id, minutes), var, 10)

    return look


def worker(id, **kw):
    kw.setdefault("shifts", list(DAY))
    return Worker(id, **kw)


def entry(id, at=0, tier=APPOINTMENT, service="cut", booked=0, **kw):
    return Entry(id, service, tier, T + at * MIN, T - 60 * MIN + booked * MIN, customer_key=id, **kw)


def starts(preds, *ids):
    return [None if preds[i].start is None else int((preds[i].start - T) / MIN) for i in ids]


def test_empty_queue_and_no_workers():
    assert predict(T, [worker("w")], [], CFG, durations()) == {}
    p = predict(T, [], [entry("a")], CFG, durations())
    assert p["a"].state == "UNSERVABLE" and p["a"].reason == "NO_ELIGIBLE_WORKER"


def test_one_worker_serves_in_order():
    p = predict(T, [worker("w")], [entry("b", 0, booked=5), entry("a", 0), entry("c", 10)], CFG, durations())
    assert starts(p, "a", "b", "c") == [0, 30, 60]
    assert [p[i].position for i in "abc"] == [1, 2, 3]
    assert [p[i].people_ahead for i in "abc"] == [0, 1, 2]
    assert p["a"].state == "YOUR_TURN" and p["b"].state == "WAITING"
    assert (p["c"].wait_min, p["c"].wait_max, p["c"].confidence) == (60, 60, "HIGH")
    assert p["c"].running_late_minutes == 0  # no booked time given


def test_two_workers_in_parallel_and_the_one_in_progress_holds_its_worker():
    jobs = [entry("x", -20, state=SERVING, worker_id="w1", started_at=T - 20 * MIN), entry("a"), entry("b"), entry("c")]
    p = predict(T, [worker("w1"), worker("w2")], jobs, CFG, durations())
    assert p["x"].state == SERVING and p["x"].eta_max == T + 10 * MIN
    assert starts(p, "a", "b", "c") == [0, 10, 30]
    assert (p["a"].worker_id, p["b"].worker_id, p["c"].worker_id) == ("w2", "w1", "w2")


def test_overrun_pushes_everyone_behind_and_is_flagged():
    started = T - 50 * MIN  # a 30-minute job, 20 minutes over
    jobs = [entry("x", -50, state=SERVING, worker_id="w", started_at=started), entry("a"), entry("b")]
    p = predict(T, [worker("w")], jobs, CFG, durations())
    assert p["x"].overrun
    assert starts(p, "a", "b") == [1, 31]  # it ends no sooner than a minute from now


def test_vip_before_appointment_before_walk_in_and_aging_lifts_walk_ins():
    jobs = [entry("walk", -5, WALK_IN), entry("appt", 0, APPOINTMENT), entry("vip", 0, VIP), entry("first", -10)]
    p = predict(T, [worker("w")], jobs, CFG, durations())
    assert [p[i].position for i in ("vip", "first", "appt", "walk")] == [1, 2, 3, 4]
    assert starts(p, "vip", "first", "appt", "walk") == [0, 30, 60, 90]

    # A walk-in who has waited past the aging limit is served like an appointment (earlier ready wins).
    aging = Config(buffer_pct=0.0, no_show_rate=0.0, aging_minutes=15)
    p = predict(T, [worker("w")], [entry("walk", -20, WALK_IN), entry("appt", 0)], aging, durations())
    assert starts(p, "walk", "appt") == [0, 30]
    p = predict(T, [worker("w")], [entry("walk", -5, WALK_IN), entry("appt", 0)], aging, durations())
    assert starts(p, "appt", "walk") == [0, 30]


def test_aging_never_lets_an_appointment_jump_a_walk_in_who_waited_longer():
    # Found by the simulator: a walk-in waiting since 10:10 must not lose to a 11:15 appointment that
    # has waited 20 minutes itself (aging only brings walk-ins up to the appointments).
    aging = Config(buffer_pct=0.0, no_show_rate=0.0, aging_minutes=20)
    jobs = [
        entry("busy", -40, state=SERVING, worker_id="w", started_at=T - 20 * MIN),
        entry("walk", -80, WALK_IN),
        entry("late-appt", -25),
        entry("vip", -5, VIP),
    ]
    p = predict(T, [worker("w")], jobs, aging, durations())
    assert starts(p, "vip", "walk", "late-appt") == [10, 40, 70]


def test_a_manual_reorder_comes_first():
    p = predict(T, [worker("w")], [entry("a"), entry("b", rank=1.0)], CFG, durations())
    assert starts(p, "b", "a") == [0, 30]


def test_skills_decide_who_serves_whom():
    workers = [worker("barber", skills=frozenset({"cut"})), worker("colour", skills=frozenset({"dye"}))]
    jobs = [
        entry("a", service="cut"),
        entry("b", service="cut"),
        entry("c", service="dye"),
        entry("d", service="nails"),
    ]
    p = predict(T, workers, jobs, CFG, durations())
    assert (p["a"].worker_id, p["b"].worker_id, p["c"].worker_id) == ("barber", "barber", "colour")
    assert starts(p, "a", "b", "c") == [0, 30, 0]
    assert p["b"].ahead_on_worker == 1 and p["c"].ahead_on_worker == 0
    assert p["d"].state == "UNSERVABLE" and p["d"].reason == "NO_ELIGIBLE_WORKER"


def test_preferred_worker_is_kept_unless_they_are_off():
    jobs = [entry("a"), entry("b", preferred_worker_id="w1")]
    p = predict(T, [worker("w1"), worker("w2")], jobs, CFG, durations())
    assert (p["a"].worker_id, p["b"].worker_id) == ("w2", "w1")  # w2 takes a so b gets w1 at once

    p = predict(
        T,
        [worker("w1"), worker("w2")],
        [entry("a", preferred_worker_id="w1"), entry("b", preferred_worker_id="w1")],
        CFG,
        durations(),
    )
    assert starts(p, "a", "b") == [0, 30] and p["b"].worker_id == "w1"  # waits for w1 although w2 is free

    p = predict(T, [worker("w1", status=OFF), worker("w2")], [entry("a", preferred_worker_id="w1")], CFG, durations())
    assert p["a"].worker_id == "w2" and p["a"].reason == "PREFERRED_UNAVAILABLE"
    p = predict(
        T,
        [worker("w1", status=OFF), worker("w2")],
        [entry("a", preferred_worker_id="w1", strict_preferred=True)],
        CFG,
        durations(),
    )
    assert p["a"].state == "UNSERVABLE"


def test_breaks_and_status_break():
    # A break from +40 to +60: the second job (30 min from +30) would run into it, so it starts at +60.
    w = worker("w", breaks=[(T + 40 * MIN, T + 60 * MIN)])
    p = predict(T, [w], [entry("a"), entry("b")], CFG, durations())
    assert starts(p, "a", "b") == [0, 60]

    # Everyone on break until +15: nobody starts before then.
    ws = [
        worker("w1", status=ON_BREAK, status_until=T + 15 * MIN),
        worker("w2", status=ON_BREAK, status_until=T + 15 * MIN),
    ]
    p = predict(T, ws, [entry("a"), entry("b")], CFG, durations())
    assert starts(p, "a", "b") == [15, 15]

    # All off: nobody is served today.
    p = predict(T, [worker("w", status=OFF)], [entry("a")], CFG, durations())
    assert p["a"].state == "UNSERVABLE"


def test_shift_end_and_a_shorter_job_that_still_fits():
    w = worker("w", shifts=[(T - 60 * MIN, T + 45 * MIN)])
    jobs = [entry("a"), entry("long", 1, service="colour"), entry("short", 2, service="trim")]
    p = predict(T, [w], jobs, CFG, durations(by_service={"colour": 60, "trim": 10}))
    assert starts(p, "a", "short") == [0, 30]
    assert p["long"].state == "UNSERVABLE" and p["long"].reason == "BEYOND_SHIFT"


def test_split_shift_waits_for_the_second_part():
    w = worker("w", shifts=[(T - 60 * MIN, T + 30 * MIN), (T + 90 * MIN, T + 300 * MIN)])
    p = predict(T, [w], [entry("a"), entry("b")], CFG, durations())
    assert starts(p, "a", "b") == [0, 90]


def test_load_cap():
    ws = [worker("w1", load_cap_minutes=60, minutes_done=30), worker("w2")]
    p = predict(T, ws, [entry(i) for i in "abcd"], CFG, durations())
    assert sum(1 for i in "abcd" if p[i].worker_id == "w1") == 1


def test_customer_not_ready_yet_waits_for_their_time():
    p = predict(T, [worker("w")], [entry("a", 45)], CFG, durations())
    assert starts(p, "a") == [45] and p["a"].wait_min == 45


def test_running_late_against_the_booked_time():
    p = predict(T, [worker("w")], [entry("a"), entry("b", scheduled_at=T)], CFG, durations())
    assert p["b"].running_late_minutes == 30


def test_eta_range_widens_with_the_jobs_ahead_and_no_shows_pull_it_earlier():
    cfg = Config(buffer_pct=0.0, no_show_rate=0.0, z=1.0, aging_minutes=10_000)
    p = predict(T, [worker("w")], [entry(i) for i in "abcde"], cfg, durations(var=25.0))  # sd 5 per job
    assert p["a"].wait_min == 0 and p["a"].wait_max <= 1
    e = p["e"]  # 4 jobs ahead: sd 10
    assert (e.wait_min, e.wait_max) == (110, 130)
    assert (p["b"].confidence, e.confidence) == ("MEDIUM", "HIGH")  # +-5 on 30 min; +-10 on 2 hours

    cfg.no_show_rate = 0.1
    e2 = predict(T, [worker("w")], [entry(i) for i in "abcde"], cfg, durations(var=25.0))["e"]
    assert e2.wait_min == 98 and e2.wait_max == 130  # 10% of 120 minutes ahead come off the low end


def test_buffer_is_added_to_planned_durations():
    p = predict(T, [worker("w")], [entry("a"), entry("b")], Config(buffer_pct=0.2, no_show_rate=0.0), durations())
    assert starts(p, "b") == [36]


def test_duration_model_learns_from_actual_durations():
    m = DurationModel(30.0)
    m = m.update(40, 0.3)  # first actual replaces the nominal
    assert (m.mean, m.var, m.n) == (40, 0.0, 1)
    m = m.update(30, 0.3)
    assert round(m.mean, 6) == 37.0 and round(m.var, 6) == 21.0
    for _ in range(200):
        m = m.update(25, 0.3)
    assert abs(m.mean - 25) < 1e-6 and m.std < 1e-3


def test_ties_are_deterministic():
    jobs = [entry(i) for i in "dcba"]
    a = predict(T, [worker("w1"), worker("w2")], jobs, CFG, durations())
    b = predict(T, [worker("w2"), worker("w1")], list(reversed(jobs)), CFG, durations())
    assert {k: (v.start, v.worker_id) for k, v in a.items()} == {k: (v.start, v.worker_id) for k, v in b.items()}


def _day(n, seed=1):
    rnd = random.Random(seed)
    workers = [worker(f"w{i}", skills=frozenset(rnd.sample(["cut", "dye", "nails", "beard"], 2))) for i in range(5)]
    services = ["cut", "dye", "nails", "beard"]
    jobs = [
        entry(
            f"e{i:03}",
            rnd.randint(-30, 240),
            rnd.choice([VIP, APPOINTMENT, WALK_IN, WALK_IN]),
            rnd.choice(services),
            booked=i,
        )
        for i in range(n)
    ]
    return workers, jobs


def test_removing_a_customer_replays_from_their_step_and_matches_a_full_recompute():
    workers, jobs = _day(60)
    dur = durations(var=16.0, by_service={"dye": 50, "nails": 20})
    cfg = Config(aging_minutes=20)
    engine = QueueEngine(cfg, dur)
    engine.predict(T, workers, jobs)
    for victim in ("e010", "e033", "e059"):
        changed = engine.remove(victim)
        jobs = [j for j in jobs if j.id != victim]
        full = predict(T, workers, jobs, cfg, dur)
        assert victim not in engine.predictions
        assert {k: v.bucket() + (v.start,) for k, v in engine.predictions.items()} == {
            k: v.bucket() + (v.start,) for k, v in full.items()
        }
        assert all(engine.predictions[k].bucket() == v.bucket() for k, v in changed.items())


def test_removing_the_one_in_service_frees_their_worker():
    jobs = [entry("x", -10, state=SERVING, worker_id="w", started_at=T - 10 * MIN), entry("a")]
    engine = QueueEngine(CFG, durations())
    assert starts(engine.predict(T, [worker("w")], jobs), "a") == [20]
    changed = engine.remove("x")
    assert starts(engine.predictions, "a") == [0] and "a" in changed


def test_200_customers_recompute_under_100_ms():
    workers, jobs = _day(200, seed=7)
    engine = QueueEngine(Config(), durations(var=9.0))
    engine.predict(T, workers, jobs)  # warm up
    began = time.perf_counter()
    engine.predict(T, workers, jobs)
    assert time.perf_counter() - began < 0.1
