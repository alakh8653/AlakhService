class AdminServiceError(Exception):
    pass

class AdminUserNotFoundError(AdminServiceError):
    def __init__(self, msg="Admin user not found"):
        super().__init__(msg)

class UnauthorizedError(AdminServiceError):
    def __init__(self, msg="Unauthorized"):
        super().__init__(msg)
