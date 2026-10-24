"""The current Terms and Privacy Policy, for the apps' sign-up screens and settings (public)."""

from fastapi import APIRouter, Response

from app.config import settings
from app.schemas.auth import LegalInfo

router = APIRouter()


def legal_info() -> LegalInfo:
    base = settings.LEGAL_BASE_URL.rstrip("/")
    return LegalInfo(
        terms_version=settings.TERMS_VERSION,
        privacy_url=f"{base}/privacy",
        terms_url=f"{base}/terms",
        refund_url=f"{base}/refunds",
        grievance_url=f"{base}/grievance",
    )


@router.get("/legal/current", response_model=LegalInfo)
async def current_legal(response: Response):
    """Send terms_version back as accepted_terms_version when registering."""
    response.headers["Cache-Control"] = "public, max-age=300"
    return legal_info()
