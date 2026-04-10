class CatalogServiceError(Exception):
    pass

class ServiceListingNotFoundError(CatalogServiceError):
    def __init__(self, msg="Service listing not found"):
        super().__init__(msg)

class CategoryNotFoundError(CatalogServiceError):
    def __init__(self, msg="Category not found"):
        super().__init__(msg)
