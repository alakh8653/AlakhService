class QueueServiceError(Exception):
    pass

class QueueNotFoundError(QueueServiceError):
    def __init__(self, msg="Queue not found"):
        super().__init__(msg)

class QueueFullError(QueueServiceError):
    def __init__(self, msg="Queue is full"):
        super().__init__(msg)

class EntryNotFoundError(QueueServiceError):
    def __init__(self, msg="Queue entry not found"):
        super().__init__(msg)
