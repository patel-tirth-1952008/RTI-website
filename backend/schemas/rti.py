# backend/schemas/rti.py

from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from config.constants import (
    ApplicationStatus, IssueCategory, DepartmentType
)


class RTICreateRequest(BaseModel):
    """Request to create an RTI application."""
    issue_description: str
    issue_location: str
    issue_city: Optional[str] = None
    issue_state: Optional[str] = None
    issue_district: Optional[str] = None
    issue_pincode: Optional[str] = None
    issue_ward_number: Optional[str] = None
    issue_latitude: Optional[float] = None
    issue_longitude: Optional[float] = None
    category: Optional[IssueCategory] = None  # Auto-detected if not provided
    language: str = "en"
    user_notes: Optional[str] = None
    custom_questions: Optional[List[str]] = None  # User can add their own

    @field_validator("issue_description")
    @classmethod
    def validate_description(cls, v):
        if len(v.strip()) < 20:
            raise ValueError(
                "Issue description must be at least 20 characters"
            )
        if len(v) > 5000:
            raise ValueError(
                "Issue description must be less than 5000 characters"
            )
        return v.strip()

    @field_validator("issue_location")
    @classmethod
    def validate_location(cls, v):
        if len(v.strip()) < 5:
            raise ValueError(
                "Location must be at least 5 characters"
            )
        return v.strip()


class RTIGenerateResponse(BaseModel):
    """Response after RTI is generated."""
    tracking_number: str
    status: ApplicationStatus
    category: IssueCategory
    department_type: Optional[DepartmentType]
    department_name: Optional[str]
    pio_name: Optional[str]
    pio_address: Optional[str]
    generated_subject: str
    generated_body: str
    generated_questions: List[str]
    generated_pdf_url: Optional[str]
    ai_category_confidence: Optional[float]
    ai_department_confidence: Optional[float]
    image_authenticity_score: Optional[float]
    estimated_fee: float
    portal_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class RTIFileRequest(BaseModel):
    """Request to file the RTI on the portal."""
    tracking_number: str
    filing_method: str = "online"  # "online" or "offline"
    # If online, optionally provide portal credentials
    portal_username: Optional[str] = None
    portal_password: Optional[str] = None
    # User can modify the generated text before filing
    final_subject: Optional[str] = None
    final_body: Optional[str] = None


class RTIFileResponse(BaseModel):
    """Response after RTI is filed."""
    tracking_number: str
    portal_reference_number: Optional[str]
    status: ApplicationStatus
    filing_date: Optional[datetime]
    response_due_date: Optional[datetime]
    portal_name: Optional[str]
    message: str


class RTIStatusResponse(BaseModel):
    """Response for status check."""
    tracking_number: str
    portal_reference_number: Optional[str]
    status: ApplicationStatus
    category: IssueCategory
    department_name: Optional[str]
    filing_date: Optional[datetime]
    response_due_date: Optional[datetime]
    response_received_date: Optional[datetime]
    response_summary: Optional[str]
    days_remaining: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RTIListResponse(BaseModel):
    """Paginated list of RTI applications."""
    total: int
    page: int
    per_page: int
    applications: List[RTIStatusResponse]


class RTIAnalysisResult(BaseModel):
    """Result of AI analysis of the issue."""
    detected_category: IssueCategory
    category_confidence: float
    detected_department: DepartmentType
    department_confidence: float
    detected_issues: List[str]
    severity: str  # "low", "medium", "high", "critical"
    recommended_questions: List[str]
    image_description: Optional[str] = None