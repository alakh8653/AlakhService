from fastapi import HTTPException, status


class CredentialsException(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


class PermissionDeniedException(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )


class NotFoundException(HTTPException):
    def __init__(self, resource_name: str = "Resource") -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_name} not found",
        )


class AlreadyExistsException(HTTPException):
    def __init__(self, resource_name: str = "Resource") -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{resource_name} already exists",
        )


class PaymentException(HTTPException):
    def __init__(self, detail: str = "Payment processing error") -> None:
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=detail,
        )


class BookingException(HTTPException):
    def __init__(self, detail: str = "Booking operation not allowed") -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )
