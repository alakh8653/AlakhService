import pytest
import pytest_asyncio
import os
import sys
import math

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base
from app.services.pricing_service import PricingService
from app.schemas.pricing import PriceCalculationRequest, CouponCreate
from app.core.rules import PricingContext, SurgePricingRule, PeakHourRule, CustomerTierRule, CouponRule, PricingEngine

pytest_plugins = ("anyio",)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
def service():
    return PricingService()


@pytest.mark.anyio
async def test_surge_pricing_calculation():
    ctx = PricingContext(base_price_cents=1000, service_id="svc-1", demand_level=3.0, supply_level=1.0)
    rule = SurgePricingRule()
    result = rule.apply(ctx)
    assert result.final_price_cents > 1000
    assert any("surge" in r for r in result.applied_rules)


@pytest.mark.anyio
async def test_no_surge_below_threshold():
    ctx = PricingContext(base_price_cents=1000, service_id="svc-1", demand_level=1.1, supply_level=1.0)
    rule = SurgePricingRule()
    result = rule.apply(ctx)
    assert result.final_price_cents == 1000
    assert result.applied_rules == []


@pytest.mark.anyio
async def test_peak_hour_rule():
    ctx = PricingContext(base_price_cents=1000, service_id="svc-1", time_of_day=8)
    rule = PeakHourRule()
    result = rule.apply(ctx)
    assert result.final_price_cents == 1150  # 15% increase
    assert result.is_peak_hour is True
    assert "peak_hour:+15%" in result.applied_rules


@pytest.mark.anyio
async def test_non_peak_hour_rule():
    ctx = PricingContext(base_price_cents=1000, service_id="svc-1", time_of_day=14)
    rule = PeakHourRule()
    result = rule.apply(ctx)
    assert result.final_price_cents == 1000


@pytest.mark.anyio
async def test_customer_tier_vip():
    ctx = PricingContext(base_price_cents=1000, service_id="svc-1", customer_tier="vip")
    rule = CustomerTierRule()
    result = rule.apply(ctx)
    assert result.final_price_cents == 900  # 10% discount
    assert any("tier_discount" in r for r in result.applied_rules)


@pytest.mark.anyio
async def test_coupon_application():
    ctx = PricingContext(base_price_cents=1000, service_id="svc-1", coupon_code="SAVE20", coupon_discount_pct=0.20)
    rule = CouponRule()
    result = rule.apply(ctx)
    assert result.final_price_cents == 800  # 20% off
    assert any("coupon" in r for r in result.applied_rules)


@pytest.mark.anyio
async def test_chain_of_responsibility():
    engine = PricingEngine()
    ctx = PricingContext(
        base_price_cents=1000,
        service_id="svc-1",
        demand_level=2.0,
        supply_level=1.0,
        time_of_day=8,
        customer_tier="premium",
        coupon_code="SAVE10",
        coupon_discount_pct=0.10,
    )
    result = engine.calculate(ctx)
    # Should have applied: surge, peak_hour, tier_discount, coupon
    assert len(result.applied_rules) >= 3
    assert result.final_price_cents < result.base_price_cents * 2  # sanity check


@pytest.mark.anyio
async def test_calculate_price_db(db_session, service):
    calc = await service.calculate_price(db_session, PriceCalculationRequest(
        service_id="svc-1", customer_id="cust-1", base_price_cents=5000,
        demand_level=1.0, supply_level=1.0, time_of_day=14, customer_tier="regular"
    ))
    assert calc.base_price_cents == 5000
    assert calc.final_price_cents == 5000  # no rules triggered at noon, normal demand


@pytest.mark.anyio
async def test_coupon_validate(db_session, service):
    await service.create_coupon(db_session, CouponCreate(code="TEST10", discount_pct=0.10, max_uses=100))
    result = await service.validate_coupon(db_session, "TEST10")
    assert result.is_valid is True
    assert result.discount_pct == 0.10
