class ComplianceServiceError(Exception):
    pass

class ExportRequestNotFoundError(ComplianceServiceError):
    def __init__(self, msg="Export request not found"):
        super().__init__(msg)

class ErasureRequestNotFoundError(ComplianceServiceError):
    def __init__(self, msg="Erasure request not found"):
        super().__init__(msg)
