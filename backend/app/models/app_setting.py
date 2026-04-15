"""Generic key/value app settings table.

Stores user-editable runtime settings (LLM provider, API keys, models).
Sensitive values are stored Fernet-encrypted; the `encrypted` flag tells
the service layer whether to decrypt on read.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    encrypted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
