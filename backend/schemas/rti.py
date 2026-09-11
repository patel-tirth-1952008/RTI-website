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
    category: Optional[IssueCategory] = None
    language: str = "en"
    user_notes: Optional[str] = None
    custom_questions: Optional[List[str]] = None

    @field_validator("issue_description")
    @classmethod
    def validate_description(cls, v):
        if len(v.strip()) < 10:
            raise ValueError(
                "Issue description must be at least 10 characters"
            )
        if len(v) > 5000:
            raise ValueError(
                "Issue description must be less than 5000 characters"
            )
        return v.strip()

    @field_validator("issue_location")
    @classmethod
    def validate_location(cls, v):
        if len(v.strip()) < 3:
            raise ValueError(
                "Location must be at least 3 characters"
            )
        return v.strip()


class RTIGenerateResponse(BaseModel):
    """Response after RTI is generated."""
    tracking_number: str
    status: ApplicationStatus
    category: IssueCategory
    department_type: Optional[DepartmentType] = None
    department_name: Optional[str] = None
    pio_name: Optional[str] = None
    pio_address: Optional[str] = None
    generated_subject: str
    generated_body: str
    generated_questions: List[str]
    generated_pdf_url: Optional[str] = None
    ai_category_confidence: Optional[float] = None
    ai_department_confidence: Optional[float] = None
    image_authenticity_score: Optional[float] = None
    estimated_fee: float = 10.0
    portal_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RTIFileRequest(BaseModel):
    """Request to file the RTI on the portal."""
    tracking_number: str
    filing_method: str = "online"
    portal_username: Optional[str] = None
    portal_password: Optional[str] = None
    final_subject: Optional[str] = None
    final_body: Optional[str] = None


class RTIFileResponse(BaseModel):
    """Response after RTI is filed."""
    tracking_number: str
    portal_reference_number: Optional[str] = None
    status: ApplicationStatus
    filing_date: Optional[datetime] = None
    response_due_date: Optional[datetime] = None
    portal_name: Optional[str] = None
    message: str


class RTIStatusResponse(BaseModel):
    """Response for status check."""
    tracking_number: str
    portal_reference_number: Optional[str] = None
    status: ApplicationStatus
    category: IssueCategory
    department_name: Optional[str] = None
    filing_date: Optional[datetime] = None
    response_due_date: Optional[datetime] = None
    response_received_date: Optional[datetime] = None
    response_summary: Optional[str] = None
    days_remaining: Optional[int] = None
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
    severity: str
    recommended_questions: List[str]
    image_description: Optional[str] = None