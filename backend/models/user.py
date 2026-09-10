import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, Enum as SQLEnum,
    Integer, Index, ForeignKey
)
from sqlalchemy.orm import relationship
from config.database import Base
from config.constants import UserRole


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_email", "email", unique=True),
        Index("idx_users_phone", "phone"),
        Index("idx_users_aadhaar_hash", "aadhaar_hash"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    hashed_password = Column(String(255), nullable=False)

    # Personal Info (Encrypted at rest)
    full_name_encrypted = Column(Text, nullable=False)
    address_encrypted = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    district = Column(String(100), nullable=True)

    # Identity verification
    aadhaar_hash = Column(String(64), nullable=True)  # SHA-256 hash only
    is_bpl = Column(Boolean, default=False)  # Below Poverty Line

    # Role & Status
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Rate limiting
    daily_rti_count = Column(Integer, default=0)
    daily_rti_reset_date = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    applications = relationship(
        "RTIApplication", back_populates="user", lazy="selectin"
    )
    sessions = relationship(
        "UserSession", back_populates="user", lazy="selectin"
    )
    api_keys = relationship(
        "APIKey", back_populates="user", lazy="selectin"
    )
    audit_logs = relationship(
        "AuditLog", back_populates="user", lazy="selectin"
    )

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("idx_sessions_user_id", "user_id"),
        Index("idx_sessions_token_hash", "refresh_token_hash"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    refresh_token_hash = Column(String(64), nullable=False)
    device_info = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="sessions")


class APIKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        Index("idx_api_keys_hash", "key_hash", unique=True),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    key_hash = Column(String(64), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    expires_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="api_keys")