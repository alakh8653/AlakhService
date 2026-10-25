from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel


class Settlement(BaseModel):
    """Escrowed funds for one payment and whether they have been paid out to the provider."""

    id: str
    payment_id: str
    booking_id: str
    payee_id: str
    amount_cents: int
    currency: str
    status: str  # CREATED, HELD, RELEASED, REFUNDED
    held_at: datetime
    released_at: Optional[datetime] = None


class SettlementList(BaseModel):
    data: List[Settlement]
    total: int
    page: int
    per_page: int


class RevenuePoint(BaseModel):
    date: date
    gross_cents: int
    refunds_cents: int
    net_cents: int
    payments: int


class RevenueReport(BaseModel):
    currency: str
    date_from: date
    date_to: date
    gross_cents: int
    refunds_cents: int
    net_cents: int
    payments: int
    series: List[RevenuePoint]
