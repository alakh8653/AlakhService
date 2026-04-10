class TrackingServiceError(Exception):
    pass

class LocationNotFoundError(TrackingServiceError):
    def __init__(self, msg="Location not found"):
        super().__init__(msg)

class GeofenceNotFoundError(TrackingServiceError):
    def __init__(self, msg="Geofence not found"):
        super().__init__(msg)
