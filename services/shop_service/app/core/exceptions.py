class ShopServiceError(Exception):
    pass

class ShopNotFoundError(ShopServiceError):
    def __init__(self, msg="Shop not found"):
        super().__init__(msg)

class ShopAlreadyExistsError(ShopServiceError):
    def __init__(self, msg="Shop already exists"):
        super().__init__(msg)


class StaffNotFoundError(ShopServiceError):
    def __init__(self, msg="Staff member not found"):
        super().__init__(msg)


class RatingExistsError(ShopServiceError):
    def __init__(self, msg="This booking has already been rated"):
        super().__init__(msg)
