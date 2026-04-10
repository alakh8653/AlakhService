class NotificationServiceError(Exception):
    pass

class NotificationNotFoundError(NotificationServiceError):
    def __init__(self, msg="Notification not found"):
        super().__init__(msg)

class TemplateNotFoundError(NotificationServiceError):
    def __init__(self, msg="Template not found"):
        super().__init__(msg)

class InvalidChannelError(NotificationServiceError):
    def __init__(self, msg="Invalid channel"):
        super().__init__(msg)

class DeliveryFailedError(NotificationServiceError):
    def __init__(self, msg="Delivery failed"):
        super().__init__(msg)

class QuietHoursError(NotificationServiceError):
    def __init__(self, msg="User is in quiet hours"):
        super().__init__(msg)
