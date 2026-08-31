from app.infrastructure.db.base import Base
from app.infrastructure.db.models.mixins import TimestampMixin
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship


class GarminCredential(TimestampMixin, Base):
    """Encrypted Garmin session material used by both API and worker."""

    __tablename__ = "garmin_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    email_encrypted: Mapped[str] = mapped_column(String(4096), nullable=False)
    token_json_encrypted: Mapped[str] = mapped_column(String(16384), nullable=False)
    external_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    connection_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="connected"
    )

    user = relationship("User", back_populates="garmin_credential")
