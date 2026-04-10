from enum import Enum
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass, field


class BookingStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    ASSIGNED = "ASSIGNED"
    PROVIDER_EN_ROUTE = "PROVIDER_EN_ROUTE"
    IN_PROGRESS = "IN_PROGRESS"
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
