import pytest
import pytest_asyncio
import os
import sys

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base
from app.services.trust_risk_service import TrustRiskService
from app.schemas.trust_risk import RiskSignalCreate
from app.core.risk_engine import BayesianRiskScorer

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
    return TrustRiskService()


@pytest.mark.anyio
async def test_bayesian_scoring_low_risk():
    scorer = BayesianRiskScorer()
    # 0 risk events, 10 safe events
    score = scorer.compute_score(0, 10, 0.0)
    # prior_alpha=1, prior_beta=9+10=19; score = 1/20 = 0.05
    assert score < 0.2
    assert scorer.risk_level(score) == "LOW"


@pytest.mark.anyio
async def test_bayesian_scoring_high_risk():
    scorer = BayesianRiskScorer()
    # Many risk events
    score = scorer.compute_score(20, 0, 0.0)
    # prior_alpha=1+20=21, prior_beta=9; score=21/30=0.7
    assert score >= 0.5
    assert scorer.risk_level(score) in ("HIGH", "CRITICAL")


@pytest.mark.anyio
async def test_ema_update():
    scorer = BayesianRiskScorer(ema_decay=0.1)
    ema = scorer.update_ema(0.0, 1.0)
    # ema = 0.1 * 1.0 + 0.9 * 0.0 = 0.1
    assert abs(ema - 0.1) < 0.001
    ema2 = scorer.update_ema(ema, 1.0)
    # ema2 = 0.1 * 1.0 + 0.9 * 0.1 = 0.19
    assert abs(ema2 - 0.19) < 0.001


@pytest.mark.anyio
async def test_risk_level_categorization():
    scorer = BayesianRiskScorer()
    assert scorer.risk_level(0.1) == "LOW"
    assert scorer.risk_level(0.3) == "MEDIUM"
    assert scorer.risk_level(0.6) == "HIGH"
    assert scorer.risk_level(0.9) == "CRITICAL"


@pytest.mark.anyio
async def test_signal_recording_increases_risk(db_session, service):
    profile = await service.get_or_create_profile(db_session, "user-1")
    initial_score = profile.risk_score

    # Record a risk event
    updated = await service.record_signal(db_session, "user-1", RiskSignalCreate(signal_type="fraud_attempt", value=1.0, is_risk_event=True))
    assert updated.risk_events == 1
    assert updated.risk_score >= initial_score


@pytest.mark.anyio
async def test_safe_signals_lower_risk(db_session, service):
    # Record many safe events
    for i in range(5):
        await service.record_signal(db_session, "user-2", RiskSignalCreate(signal_type="successful_payment", value=0.0, is_risk_event=False))
    
    profile = await service.get_or_create_profile(db_session, "user-2")
    assert profile.safe_events == 5
    assert profile.risk_score < 0.5


@pytest.mark.anyio
async def test_signal_history(db_session, service):
    await service.record_signal(db_session, "user-3", RiskSignalCreate(signal_type="login_from_new_device", value=0.5, is_risk_event=True))
    await service.record_signal(db_session, "user-3", RiskSignalCreate(signal_type="payment_success", value=0.0, is_risk_event=False))
    history = await service.get_signal_history(db_session, "user-3")
    assert len(history) == 2
