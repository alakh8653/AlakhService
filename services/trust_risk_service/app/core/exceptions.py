class TrustRiskServiceError(Exception):
    pass

class UserRiskProfileNotFoundError(TrustRiskServiceError):
    def __init__(self, msg="User risk profile not found"):
        super().__init__(msg)
