"""What a waiting customer is told, from what changed since they were last told."""

from datetime import datetime, timedelta, timezone

from app.core.live_queue import IN_PROGRESS, WAITING_STATE, YOUR_TURN, QueueSpot
from app.core.queue_notify import MAX_PER_DAY, decide

T = datetime(2030, 11, 4, 5, 0, tzinfo=timezone.utc)  # 10:30 in India
MIN = timedelta(minutes=1)
RULES = {"turn_soon_minutes": 15, "running_late_minutes": 15, "zone": "Asia/Kolkata"}


def spot(ahead, wait, late=0, state=WAITING_STATE, at=0):
    """Their place seen [at] minutes after T: [wait] minutes from then."""
    start = T + (at + wait) * MIN
    return QueueSpot("b", state, ahead + 1, ahead, 1, start, start + 30 * MIN, wait, late)


def run(steps, state=None, **kw):
    """[(minutes from T, people ahead, wait, ...)] -> the kinds sent, in order."""
    state, kinds = state or {}, []
    for minutes, *place in steps:
        notice, state = decide(state, spot(*place, at=minutes), T + minutes * MIN, **{**RULES, **kw})
        kinds.append(notice.kind if notice else None)
    return kinds, state


def test_moving_up_the_line_each_step_once_then_soon_then_their_turn():
    kinds, _ = run(
        [
            (0, 8, 120),  # the first look: nothing yet, just the baseline
            (10, 5, 110),  # 5 ahead
            (12, 5, 108),  # nothing new
            (30, 3, 90),  # still within "5 ahead": told already
            (60, 2, 60),  # 2 ahead
            (106, 0, 14),  # about 14 min to go
            (118, 0, 2, 0, YOUR_TURN),
            (119, 0, 1, 0, YOUR_TURN),
        ]
    )
    assert kinds == [None, "queue_ahead", None, None, "queue_ahead", "turn_soon", "your_turn", None]


def test_a_delay_of_ten_minutes_or_more_is_told_with_why_and_earlier_too():
    notice, state = decide({}, spot(6, 60), T, **RULES)
    assert notice is None
    # Expected at 11:30; six minutes later it is 11:41.
    notice, state = decide(state, spot(6, 65, at=6), T + 6 * MIN, **RULES)
    assert (notice.kind, notice.data["why"], notice.data["eta"]) == (
        "queue_update",
        "the shop is running behind",
        "11:41 AM",
    )
    notice, state = decide(state, spot(6, 45, at=20), T + 20 * MIN, **RULES, staff_name="Asha", staff_away=True)
    assert notice is None  # 11:35: within 10 minutes of what they were last told
    notice, state = decide(state, spot(6, 55, at=30), T + 30 * MIN, **RULES, staff_name="Asha", staff_away=True)
    assert (notice.kind, notice.data["why"], notice.data["eta"]) == (
        "queue_update",
        "Asha is on a short break",
        "11:55 AM",
    )
    notice, _ = decide(state, spot(6, 20, at=50), T + 50 * MIN, **RULES)  # 11:40
    assert (notice.kind, notice.data["why"]) == ("queue_update", "you may be seen sooner")


def test_running_late_against_the_booked_time_is_told_once_and_covers_the_steps_ahead():
    kinds, state = run([(0, 2, 45, 50), (10, 2, 35, 50), (20, 1, 25, 50)])
    assert kinds == ["queue_update", None, None]  # it said they were 2 ahead, too
    assert {"late", "ahead_2", "ahead_5"} <= set(state["sent"])


def test_throttle_and_daily_cap_but_their_turn_always_goes():
    _, state = run([(0, 8, 100)])
    notice, state = decide(state, spot(8, 115, at=1), T + 1 * MIN, **RULES)
    assert notice.kind == "queue_update"
    notice, state = decide(state, spot(8, 140, at=3), T + 3 * MIN, **RULES)
    assert notice is None  # within 5 minutes of the last message
    notice, state = decide(state, spot(0, 0, state=YOUR_TURN, at=4), T + 4 * MIN, **RULES, staff_name="Asha")
    assert (notice.kind, notice.data["staff_line"]) == ("your_turn", "Asha is ready for you.")
    capped = {"count": MAX_PER_DAY, "eta": (T + 10 * MIN).isoformat()}
    assert decide(capped, spot(4, 60), T, **RULES)[0] is None


def test_nothing_for_someone_being_served_or_after_a_corrupt_state():
    assert decide({}, spot(0, 0, state=IN_PROGRESS), T, **RULES)[0] is None
    from app.core.queue_notify import load

    assert load("not json") == {} and load('"a string"') == {} and load(None) == {}
