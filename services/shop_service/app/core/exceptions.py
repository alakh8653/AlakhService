class ShopServiceError(Exception):
    pass

class ShopNotFoundError(ShopServiceError):
    def __init__(self, msg="Shop not found"):
        super().__init__(msg)

class ShopAlreadyExistsError(ShopServiceError):
    def __init__(self, msg="Shop already exists"):
        super().__init__(msg)
