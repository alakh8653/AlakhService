"""Filtering and sorting what customers browse and search: by price, rating, how the service is delivered,
and how far away the shop is."""

import math
from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence

from app.models.catalog import ServiceListing

Sort = Literal["relevance", "price_asc", "price_desc", "rating", "distance"]
SORTS = ("relevance", "price_asc", "price_desc", "rating", "distance")
MODES = ("AT_SHOP", "AT_HOME", "PICKUP_DROP")


@dataclass(frozen=True)
class Discovery:
    min_price_cents: Optional[int] = None
    max_price_cents: Optional[int] = None
    # Whole or half stars; shops without ratings yet are left out once this is set.
    min_rating: Optional[float] = None
    # Only services that can be delivered this way.
    mode: Optional[str] = None
    # Where the customer is: adds distance_km to each result and enables max_km and the distance sort.
    lat: Optional[float] = None
    lng: Optional[float] = None
    max_km: Optional[float] = None
    sort: Sort = "relevance"

    @property
    def located(self) -> bool:
        return self.lat is not None and self.lng is not None


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance (haversine), in kilometres."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def where(query, d: Discovery):
    """The filters that can run in the database."""
    if d.min_price_cents is not None:
        query = query.where(ServiceListing.price_cents >= d.min_price_cents)
    if d.max_price_cents is not None:
        query = query.where(ServiceListing.price_cents <= d.max_price_cents)
    if d.min_rating is not None:
        query = query.where(ServiceListing.shop_rating >= d.min_rating, ServiceListing.shop_rating_count > 0)
    if d.mode:
        # service_modes is a comma-separated list; wrapping both in commas matches whole values only.
        query = query.where(("," + ServiceListing.service_modes + ",").like(f"%,{d.mode},%"))
    return query


def arrange(listings: Sequence[ServiceListing], d: Discovery) -> List[ServiceListing]:
    """Distance (set on each listing as distance_km), the distance limit and the sort; relevance keeps the
    order given. A shop with no location is kept unless max_km is set, and goes last when sorting by it."""
    items = list(listings)
    for item in items:
        known = d.located and item.shop_latitude is not None and item.shop_longitude is not None
        item.distance_km = (
            round(distance_km(d.lat, d.lng, item.shop_latitude, item.shop_longitude), 1) if known else None
        )
    if d.max_km is not None and d.located:
        items = [i for i in items if i.distance_km is not None and i.distance_km <= d.max_km]
    if d.sort == "price_asc":
        items.sort(key=lambda i: (i.price_cents, i.name))
    elif d.sort == "price_desc":
        items.sort(key=lambda i: (-i.price_cents, i.name))
    elif d.sort == "rating":
        # Best rated first; among equals, the one more people rated.
        items.sort(key=lambda i: (-(i.shop_rating or 0), -(i.shop_rating_count or 0), i.name))
    elif d.sort == "distance" and d.located:
        items.sort(key=lambda i: (i.distance_km is None, i.distance_km or 0, i.name))
    return items
