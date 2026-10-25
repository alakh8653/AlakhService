from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional


class BookingStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    ASSIGNED = "ASSIGNED"
    PROVIDER_EN_ROUTE = "PROVIDER_EN_ROUTE"
    # Pickup & drop: the item has been collected from the customer...
    PICKED_UP = "PICKED_UP"
    IN_PROGRESS = "IN_PROGRESS"
    # ...and, once serviced, is on its way back.
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    DISPUTED = "DISPUTED"


@dataclass
class Transition:
    from_state: BookingStatus
    to_state: BookingStatus
    guard: Optional[Callable] = None
    on_enter: Optional[Callable] = None
    on_exit: Optional[Callable] = None


class BookingFSM:
    """Finite State Machine for booking lifecycle management."""

    def __init__(self):
        self._transitions: Dict[BookingStatus, List[Transition]] = {}
        self._setup_transitions()

    def _setup_transitions(self):
        transitions = [
            Transition(BookingStatus.PENDING, BookingStatus.CONFIRMED),
            Transition(BookingStatus.PENDING, BookingStatus.CANCELLED),
            Transition(BookingStatus.CONFIRMED, BookingStatus.ASSIGNED),
            Transition(BookingStatus.CONFIRMED, BookingStatus.CANCELLED),
            Transition(BookingStatus.ASSIGNED, BookingStatus.PROVIDER_EN_ROUTE),
            Transition(BookingStatus.ASSIGNED, BookingStatus.CANCELLED),
            Transition(BookingStatus.PROVIDER_EN_ROUTE, BookingStatus.IN_PROGRESS),
            # At the shop: the customer has arrived, no provider travels.
            Transition(BookingStatus.CONFIRMED, BookingStatus.IN_PROGRESS),
            # Pickup & drop: collect the item, service it, bring it back.
            Transition(BookingStatus.ASSIGNED, BookingStatus.PICKED_UP),
            Transition(BookingStatus.PROVIDER_EN_ROUTE, BookingStatus.PICKED_UP),
            Transition(BookingStatus.PICKED_UP, BookingStatus.IN_PROGRESS),
            Transition(BookingStatus.IN_PROGRESS, BookingStatus.OUT_FOR_DELIVERY),
            Transition(BookingStatus.OUT_FOR_DELIVERY, BookingStatus.COMPLETED),
            Transition(BookingStatus.OUT_FOR_DELIVERY, BookingStatus.DISPUTED),
            Transition(BookingStatus.IN_PROGRESS, BookingStatus.COMPLETED),
            Transition(BookingStatus.IN_PROGRESS, BookingStatus.DISPUTED),
            Transition(BookingStatus.COMPLETED, BookingStatus.DISPUTED),
            Transition(BookingStatus.DISPUTED, BookingStatus.REFUNDED),
            Transition(BookingStatus.DISPUTED, BookingStatus.COMPLETED),
        ]
        for t in transitions:
            if t.from_state not in self._transitions:
                self._transitions[t.from_state] = []
            self._transitions[t.from_state].append(t)

    def can_transition(self, from_state: BookingStatus, to_state: BookingStatus) -> bool:
        for t in self._transitions.get(from_state, []):
            if t.to_state == to_state:
                return True
        return False

    def get_valid_transitions(self, state: BookingStatus) -> List[BookingStatus]:
        return [t.to_state for t in self._transitions.get(state, [])]

    def transition(self, from_state: BookingStatus, to_state: BookingStatus, context: dict = None) -> bool:
        for t in self._transitions.get(from_state, []):
            if t.to_state == to_state:
                if t.guard and not t.guard(context or {}):
                    raise ValueError(f"Guard condition failed for transition {from_state} -> {to_state}")
                if t.on_exit:
                    t.on_exit(context or {})
                if t.on_enter:
                    t.on_enter(context or {})
                return True
        raise ValueError(f"Invalid transition: {from_state} -> {to_state}")


booking_fsm = BookingFSM()

# How a booking is delivered (chosen from the service's modes when booking).
AT_SHOP, AT_HOME, PICKUP_DROP = "AT_SHOP", "AT_HOME", "PICKUP_DROP"
SERVICE_MODES = (AT_SHOP, AT_HOME, PICKUP_DROP)


def mode_problem(mode: str, from_state: BookingStatus, to_state: BookingStatus) -> Optional[str]:
    """Why this transition does not fit how the booking is delivered, or None if it does.

    The state machine allows every step any mode needs; this keeps each booking on its own path:
    pickup steps only for pickup & drop, which must collect the item before working on it and
    bring it back before completing; and straight from confirmed to started only at the shop.
    """
    pickup_steps = {BookingStatus.PICKED_UP, BookingStatus.OUT_FOR_DELIVERY}
    if mode != PICKUP_DROP and to_state in pickup_steps:
        return "Pickup and delivery steps are only for pickup & drop bookings"
    if mode == PICKUP_DROP:
        if to_state == BookingStatus.IN_PROGRESS and from_state != BookingStatus.PICKED_UP:
            return "Pick up the item before starting work on it"
        if to_state == BookingStatus.COMPLETED and from_state == BookingStatus.IN_PROGRESS:
            return "Deliver the item back to the customer first"
    if from_state == BookingStatus.CONFIRMED and to_state == BookingStatus.IN_PROGRESS and mode != AT_SHOP:
        return "Assign a provider before starting a booking away from the shop"
    return None
