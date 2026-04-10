def point_in_polygon(lat: float, lon: float, polygon: list[tuple]) -> bool:
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside

def is_in_circular_geofence(lat: float, lon: float, center_lat: float, center_lon: float, radius_meters: float) -> bool:
    import math
    R = 6371000
    phi1, phi2 = math.radians(lat), math.radians(center_lat)
    dphi = math.radians(center_lat - lat)
    dlambda = math.radians(center_lon - lon)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2*R*math.atan2(math.sqrt(a), math.sqrt(1-a)) <= radius_meters
