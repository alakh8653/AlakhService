"""What to tell a customer waiting in a shop's line, from what changed since they were last told.

Every pass of the worker recomputes the line; for each customer waiting today this compares their place
now with what was last sent to them (Booking.queue_notice_state) and picks at most one message:

  your_turn     it is their turn (once);
  turn_soon     about TURN_SOON_MINUTES to go (once);
  queue_update  their expected time moved by DELAY_MINUTES or more since they were last told (later: the
                shop is behind; their team member is on a break or away; earlier: they may be seen sooner),
                or the shop is running RUNNING_LATE_MINUTES behind their booked time (the first time);
  queue_ahead   AHEAD_STEPS people ahead of them (each step once).

A message is not repeated (each kind or step is marked sent), and none goes within THROTTLE of the last
except your_turn; at most MAX_PER_DAY reach one customer. Messages carry where they stand now, so a message
also counts for the steps it covers (a "running late" with 2 ahead also says they are 2 ahead).
Delivery, retries, quiet hours and the channel (push, in-app, SMS) are notification_service's.

Pure: decide() takes the state and returns the message and the new state, so it is easy to test.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from app.core import live_queue

AHEAD_STEPS = (5, 2)
DELAY_MINUTES = 10
THROTTLE = timedelta(minutes=5)
MAX_PER_DAY = 8


@dataclass
class Notice:
    kind: str  # your_turn, turn_soon, queue_update, queue_ahead
    data: dict


def _iso(at: Optional[datetime]) -> Optional[str]:
    return at.isoformat() if at else None


def _parse(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


def load(raw: Optional[str]) -> dict:
    try:
        state = json.loads(raw) if raw else {}
    except ValueError:
        state = {}
    return state if isinstance(state, dict) else {}


def _eta_text(at: datetime, zone: str) -> str:
    return at.astimezone(ZoneInfo(zone)).strftime("%I:%M %p").lstrip("0")


def decide(
    state: dict,
    spot: live_queue.QueueSpot,
    now: datetime,
    *,
    turn_soon_minutes: int,
    running_late_minutes: int,
    zone: str,
    staff_name: Optional[str] = None,
    staff_away: bool = False,
) -> Tuple[Optional[Notice], dict]:
    """The message to send for [spot] now (or None), and the state to keep."""
    state = {**state, "sent": list(state.get("sent", []))}
    if spot.state not in (live_queue.WAITING_STATE, live_queue.YOUR_TURN) or spot.estimated_start is None:
        return None, state
    sent = set(state["sent"])
    eta = spot.estimated_start
    told_eta = _parse(state.get("eta"))
    if told_eta is None:  # the first look: what the app shows them now is the baseline
        state["eta"] = _iso(eta)
        told_eta = eta
    last = _parse(state.get("last"))
    throttled = last is not None and now - last < THROTTLE
    exhausted = state.get("count", 0) >= MAX_PER_DAY
    data = {
        "position": spot.position,
        "people_ahead": spot.people_ahead,
        "wait_minutes": spot.wait_minutes,
        "late_minutes": spot.running_late_minutes,
        "eta": _eta_text(eta, zone),
        "staff_name": staff_name,
    }
    notice = None
    moved = (eta - told_eta).total_seconds() / 60
    if spot.state == live_queue.YOUR_TURN and "turn" not in sent:
        line = f"{staff_name} is ready for you." if staff_name else ""
        notice = Notice("your_turn", {**data, "staff_line": line})
        sent |= {"turn", "soon"}
    elif throttled or exhausted:
        return None, {**state, "sent": sorted(sent)}
    elif turn_soon_minutes > 0 and "soon" not in sent and spot.wait_minutes <= turn_soon_minutes:
        notice = Notice("turn_soon", data)
        sent |= {"soon", "late"}  # nearly their turn: a later "running late" would only confuse
    elif abs(moved) >= DELAY_MINUTES and "soon" not in sent:
        if moved < 0:
            why = "you may be seen sooner"
        elif staff_away and staff_name:
            why = f"{staff_name} is on a short break"
        else:
            why = "the shop is running behind"
        notice = Notice("queue_update", {**data, "why": why})
        sent.add("late")
    elif running_late_minutes > 0 and "late" not in sent and spot.running_late_minutes >= running_late_minutes:
        notice = Notice(
            "queue_update", {**data, "why": f"about {spot.running_late_minutes} min after your booked time"}
        )
        sent.add("late")
    else:
        step = next((n for n in sorted(AHEAD_STEPS) if spot.people_ahead <= n and f"ahead_{n}" not in sent), None)
        if step is not None and spot.people_ahead > 0:
            notice = Notice("queue_ahead", data)
    if notice is None:
        return None, {**state, "sent": sorted(sent)}
    # The message says how many are ahead: every step it covers is told.
    sent |= {f"ahead_{n}" for n in AHEAD_STEPS if spot.people_ahead <= n}
    state.update(sent=sorted(sent), eta=_iso(eta), last=_iso(now), count=state.get("count", 0) + 1)
    return notice, state
