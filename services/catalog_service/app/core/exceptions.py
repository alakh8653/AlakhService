class CatalogServiceError(Exception):
    pass

class CategoryNotFoundError(CatalogServiceError):
    def __init__(self, msg="Category not found"):
        super().__init__(msg)

class ServiceNotFoundError(CatalogServiceError):
    def __init__(self, msg="Service not found"):
        super().__init__(msg)

class SlugConflictError(CatalogServiceError):
    def __init__(self, msg="Slug already exists"):
        super().__init__(msg)
