# backend/models/rti_application.py

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, Integer, Float,
    Enum as SQLEnum, ForeignKey, JSON, Index
)
from sqlalchemy.orm import relationship
from config.database import Base
from config.constants import (
    ApplicationStatus, IssueCategory, DepartmentType
)


def generate_uuid():
    return str(uuid.uuid4())


class RTIApplication(Base):
    __tablename__ = "rti_applications"
    __table_args__ = (
        Index("idx_rti_user_id", "user_id"),
        Index("idx_rti_status", "status"),
        Index("idx_rti_tracking_number", "tracking_number", unique=True),
        Index("idx_rti_portal_ref", "portal_reference_number"),
        Index("idx_rti_created", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(
        String(36), ForeignKey("users.id"), nullable=False
    )

    # Internal tracking
    tracking_number = Column(
        String(50), unique=True, nullable=False
    )  # Our system's tracking number

    # Portal reference (from government portal after filing)
    portal_reference_number = Column(String(100), nullable=True)
    portal_name = Column(String(100), nullable=True)  # e.g., "rtionline.gov.in"

    # Issue Details
    category = Column(
        SQLEnum(IssueCategory), nullable=False
    )
    issue_description = Column(Text, nullable=False)
    issue_location = Column(Text, nullable=True)
    issue_latitude = Column(Float, nullable=True)
    issue_longitude = Column(Float, nullable=True)
    issue_city = Column(String(100), nullable=True)
    issue_state = Column(String(100), nullable=True)
    issue_district = Column(String(100), nullable=True)
    issue_pincode = Column(String(10), nullable=True)
    issue_ward_number = Column(String(20), nullable=True)

    # Department
    department_type = Column(SQLEnum(DepartmentType), nullable=True)
    department_name = Column(String(255), nullable=True)
    pio_name = Column(String(255), nullable=True)
    pio_address = Column(Text, nullable=True)

    # Generated RTI
    generated_subject = Column(Text, nullable=True)
    generated_body = Column(Text, nullable=True)
    generated_questions = Column(JSON, nullable=True)  # List of questions
    generated_pdf_url = Column(String(500), nullable=True)

    # Filing Details
    status = Column(
        SQLEnum(ApplicationStatus),
        default=ApplicationStatus.DRAFT,
        nullable=False
    )
    filing_method = Column(
        String(20), nullable=True
    )  # "online", "offline_post", "offline_hand"
    filing_date = Column(DateTime(timezone=True), nullable=True)
    fee_paid = Column(Boolean, default=False)
    fee_amount = Column(Float, default=10.0)
    fee_transaction_id = Column(String(100), nullable=True)

    # Response tracking
    response_due_date = Column(DateTime(timezone=True), nullable=True)
    response_received_date = Column(DateTime(timezone=True), nullable=True)
    response_summary = Column(Text, nullable=True)

    # AI Analysis
    ai_category_confidence = Column(Float, nullable=True)
    ai_department_confidence = Column(Float, nullable=True)
    image_authenticity_score = Column(Float, nullable=True)

    # Metadata
    language = Column(String(5), default="en")
    is_bpl_application = Column(Boolean, default=False)
    user_notes = Column(Text, nullable=True)

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

    # Relationships
    user = relationship("User", back_populates="applications")
    media_files = relationship(
        "MediaFile", back_populates="application", lazy="selectin"
    )
    responses = relationship(
        "RTIResponse", back_populates="application", lazy="selectin"
    )
    appeals = relationship(
        "Appeal", back_populates="application", lazy="selectin"
    )

    def __repr__(self):
        return (
            f"<RTIApplication(id={self.id}, "
            f"tracking={self.tracking_number}, "
            f"status={self.status})>"
        )


class RTIResponse(Base):
    __tablename__ = "rti_responses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    application_id = Column(
        String(36), ForeignKey("rti_applications.id"), nullable=False
    )
    response_date = Column(DateTime(timezone=True), nullable=False)
    response_text = Column(Text, nullable=True)
    response_document_url = Column(String(500), nullable=True)
    is_satisfactory = Column(Boolean, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    application = relationship("RTIApplication", back_populates="responses")


class Appeal(Base):
    __tablename__ = "appeals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    application_id = Column(
        String(36), ForeignKey("rti_applications.id"), nullable=False
    )
    appeal_type = Column(String(20), nullable=False)  # "first" or "second"
    appeal_reason = Column(Text, nullable=False)
    appeal_date = Column(DateTime(timezone=True), nullable=False)
    appeal_reference_number = Column(String(100), nullable=True)
    appeal_status = Column(String(50), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    application = relationship("RTIApplication", back_populates="appeals")