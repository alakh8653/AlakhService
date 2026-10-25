from enum import Enum
from typing import Dict, List


class DisputeStatus(str, Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class DisputeFSM:
    """FSM: OPEN -> UNDER_REVIEW -> RESOLVED / ESCALATED; ESCALATED -> RESOLVED"""

    TRANSITIONS: Dict[DisputeStatus, List[DisputeStatus]] = {
        DisputeStatus.OPEN: [DisputeStatus.UNDER_REVIEW, DisputeStatus.RESOLVED],
        DisputeStatus.UNDER_REVIEW: [DisputeStatus.RESOLVED, DisputeStatus.ESCALATED],
        DisputeStatus.ESCALATED: [DisputeStatus.RESOLVED],
        DisputeStatus.RESOLVED: [],
    }

    def can_transition(self, from_state: DisputeStatus, to_state: DisputeStatus) -> bool:
        return to_state in self.TRANSITIONS.get(from_state, [])

    def transition(self, from_state: DisputeStatus, to_state: DisputeStatus) -> DisputeStatus:
        if not self.can_transition(from_state, to_state):
            raise ValueError(f"Invalid transition: {from_state} -> {to_state}")
        return to_state

    def get_valid_transitions(self, state: DisputeStatus) -> List[DisputeStatus]:
        return self.TRANSITIONS.get(state, [])


dispute_fsm = DisputeFSM()
