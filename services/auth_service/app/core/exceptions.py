class AuthServiceError(Exception):
    pass


class InvalidCredentialsError(AuthServiceError):
    def __init__(self, msg="Invalid credentials"):
        super().__init__(msg)


class UserNotFoundError(AuthServiceError):
    def __init__(self, msg="User not found"):
        super().__init__(msg)


class UserAlreadyExistsError(AuthServiceError):
    def __init__(self, msg="User already exists"):
        super().__init__(msg)


class InvalidTokenError(AuthServiceError):
    def __init__(self, msg="Invalid token"):
        super().__init__(msg)


class TokenExpiredError(AuthServiceError):
    def __init__(self, msg="Token expired"):
        super().__init__(msg)


class AccountLockedError(AuthServiceError):
    def __init__(self, lockout_seconds: int, msg=None):
        self.lockout_seconds = lockout_seconds
        super().__init__(msg or f"Account locked for {lockout_seconds} seconds")


class OTPExpiredError(AuthServiceError):
    def __init__(self, msg="OTP expired"):
        super().__init__(msg)


class OTPInvalidError(AuthServiceError):
    def __init__(self, msg="Invalid OTP"):
        super().__init__(msg)


class OTPTooManyAttemptsError(AuthServiceError):
    def __init__(self, msg="Too many OTP attempts"):
        super().__init__(msg)


class UserNotVerifiedError(AuthServiceError):
    def __init__(self, msg="User not verified"):
        super().__init__(msg)
