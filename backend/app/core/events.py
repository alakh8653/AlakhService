import logging

from fastapi import FastAPI

from app.database import engine

logger = logging.getLogger(__name__)


async def on_startup(app: FastAPI) -> None:
    """Run on application startup: verify DB connectivity and log readiness."""
    logger.info("Starting up AlakhService API...")
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        logger.info("Database connection established successfully.")
    except Exception as exc:
        logger.warning("Database connection check failed: %s", exc)
    logger.info("AlakhService API is ready to serve requests.")


async def on_shutdown(app: FastAPI) -> None:
    """Run on application shutdown: close DB pool and log teardown."""
    logger.info("Shutting down AlakhService API...")
    await engine.dispose()
    logger.info("Database connections closed. Goodbye.")
