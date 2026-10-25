class KalmanGPSFilter:
    def __init__(self, process_noise=0.001, measurement_noise=0.5):
        self.q = process_noise
        self.r = measurement_noise
        self.lat_estimate = None
        self.lon_estimate = None
        self.lat_error = 1.0
        self.lon_error = 1.0

    def update(self, lat: float, lon: float, accuracy: float = 1.0) -> tuple[float, float]:
        r = self.r * accuracy
        if self.lat_estimate is None:
            self.lat_estimate, self.lon_estimate = lat, lon
            return lat, lon
        self.lat_error += self.q
        self.lon_error += self.q
        k_lat = self.lat_error / (self.lat_error + r)
        k_lon = self.lon_error / (self.lon_error + r)
        self.lat_estimate += k_lat * (lat - self.lat_estimate)
        self.lon_estimate += k_lon * (lon - self.lon_estimate)
        self.lat_error = (1 - k_lat) * self.lat_error
        self.lon_error = (1 - k_lon) * self.lon_error
        return self.lat_estimate, self.lon_estimate
