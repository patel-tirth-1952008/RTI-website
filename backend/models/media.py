# backend/models/media.py

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, Float, Integer,
    Enum as SQLEnum, ForeignKey, JSON, Index
)
from sqlalchemy.orm import relationship
from config.database import Base
from config.constants import MediaType, FraudCheckResult


def generate_uuid():
    return str(uuid.uuid4())


class MediaFile(Base):
    __tablename__ = "media_files"
    __table_args__ = (
        Index("idx_media_application_id", "application_id"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    application_id = Column(
        String(36), ForeignKey("rti_applications.id"), nullable=False
    )

    # File info
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)
    media_type = Column(SQLEnum(MediaType), nullable=False)
    mime_type = Column(String(50), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    file_hash_sha256 = Column(String(64), nullable=False)

    # Image/Video metadata
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    duration_seconds = Column(Float, nullable=True)  # For videos

    # EXIF data
    exif_data = Column(JSON, nullable=True)
    capture_date = Column(DateTime(timezone=True), nullable=True)
    camera_make = Column(String(100), nullable=True)
    camera_model = Column(String(100), nullable=True)
    gps_latitude = Column(Float, nullable=True)
    gps_longitude = Column(Float, nullable=True)

    # Fraud detection results
    fraud_check_result = Column(
        SQLEnum(FraudCheckResult), nullable=True
    )
    fraud_check_score = Column(Float, nullable=True)  # 0.0 to 1.0
    fraud_check_details = Column(JSON, nullable=True)
    is_verified = Column(Boolean, default=False)

    # AI Analysis
    ai_description = Column(Text, nullable=True)
    ai_detected_issues = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    application = relationship("RTIApplication", back_populates="media_files")
    fraud_logs = relationship(
        "FraudCheckLog", back_populates="media_file", lazy="selectin"
    )


class FraudCheckLog(Base):
    __tablename__ = "fraud_check_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    media_file_id = Column(
        String(36), ForeignKey("media_files.id"), nullable=False
    )
    check_type = Column(
        String(50), nullable=False
    )  # "exif", "ela", "hash", "ai_detection", "metadata"
    check_result = Column(SQLEnum(FraudCheckResult), nullable=False)
    confidence_score = Column(Float, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    media_file = relationship("MediaFile", back_populates="fraud_logs")