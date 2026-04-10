# Import all models here so Alembic can detect them during autogenerate
from app.models.user import User  # noqa: F401
from app.models.service import Service  # noqa: F401
from app.models.booking import Booking  # noqa: F401
from app.models.payment import Payment  # noqa: F401
from app.models.notification import Notification  # noqa: F401
