class DisputeServiceError(Exception):
    pass

class DisputeNotFoundError(DisputeServiceError):
    def __init__(self, msg="Dispute not found"):
        super().__init__(msg)

class InvalidDisputeTransitionError(DisputeServiceError):
    def __init__(self, from_state: str, to_state: str):
        super().__init__(f"Invalid transition: {from_state} -> {to_state}")
