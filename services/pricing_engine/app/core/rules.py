from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import math


@dataclass
class PricingContext:
    base_price_cents: int
    service_id: str
    customer_tier: str = "regular"  # regular, premium, vip
    demand_level: float = 1.0       # 1.0 = normal, >1 = high demand
    supply_level: float = 1.0       # 1.0 = normal, <1 = low supply
    time_of_day: int = 12           # hour 0-23
    is_peak_hour: bool = False
    coupon_code: Optional[str] = None
    coupon_discount_pct: float = 0.0
    final_price_cents: int = 0
    applied_rules: list = None

    def __post_init__(self):
        self.final_price_cents = self.base_price_cents
        if self.applied_rules is None:
            self.applied_rules = []


class PricingRule(ABC):
    @abstractmethod
    def apply(self, ctx: PricingContext) -> PricingContext:
        pass

    @property
    def name(self) -> str:
        return self.__class__.__name__


class SurgePricingRule(PricingRule):
    """Surge pricing based on demand/supply ratio with exponential smoothing."""

    def apply(self, ctx: PricingContext) -> PricingContext:
        ratio = ctx.demand_level / max(ctx.supply_level, 0.01)
        if ratio <= 1.2:
            return ctx
        alpha, beta = 0.5, 0.8
        surge_multiplier = 1.0 + alpha * math.pow(ratio - 1.0, beta)
        surge_multiplier = min(surge_multiplier, 3.0)
        ctx.final_price_cents = int(ctx.final_price_cents * surge_multiplier)
        ctx.applied_rules.append(f"surge:{surge_multiplier:.2f}x")
        return ctx


class PeakHourRule(PricingRule):
    """Apply peak hour surcharge."""
    PEAK_HOURS = {7, 8, 9, 18, 19, 20}

    def apply(self, ctx: PricingContext) -> PricingContext:
        if ctx.time_of_day in self.PEAK_HOURS:
            ctx.is_peak_hour = True
            ctx.final_price_cents = int(ctx.final_price_cents * 1.15)
            ctx.applied_rules.append("peak_hour:+15%")
        return ctx


class CustomerTierRule(PricingRule):
    """Discount for premium/VIP customers."""
    DISCOUNTS = {"premium": 0.05, "vip": 0.10}

    def apply(self, ctx: PricingContext) -> PricingContext:
        discount = self.DISCOUNTS.get(ctx.customer_tier, 0.0)
        if discount > 0:
            ctx.final_price_cents = int(ctx.final_price_cents * (1 - discount))
            ctx.applied_rules.append(f"tier_discount:-{discount*100:.0f}%")
        return ctx


class CouponRule(PricingRule):
    """Apply coupon discount."""

    def apply(self, ctx: PricingContext) -> PricingContext:
        if ctx.coupon_code and ctx.coupon_discount_pct > 0:
            discount = min(ctx.coupon_discount_pct, 0.50)
            ctx.final_price_cents = int(ctx.final_price_cents * (1 - discount))
            ctx.applied_rules.append(f"coupon:{ctx.coupon_code}:-{discount*100:.0f}%")
        return ctx


class PricingEngine:
    """Chain of responsibility pattern for pricing rules."""

    def __init__(self):
        self._rules: list[PricingRule] = [
            SurgePricingRule(),
            PeakHourRule(),
            CustomerTierRule(),
            CouponRule(),
        ]

    def calculate(self, ctx: PricingContext) -> PricingContext:
        for rule in self._rules:
            ctx = rule.apply(ctx)
        return ctx

    def add_rule(self, rule: PricingRule) -> None:
        self._rules.append(rule)


pricing_engine = PricingEngine()
