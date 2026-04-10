class DispatchServiceError(Exception):
    pass

class NoProvidersAvailableError(DispatchServiceError):
    def __init__(self, msg="No providers available"):
        super().__init__(msg)

class DispatchJobNotFoundError(DispatchServiceError):
    def __init__(self, msg="Dispatch job not found"):
        super().__init__(msg)
