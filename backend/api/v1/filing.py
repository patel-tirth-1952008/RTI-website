"""
RTI FILING API ENDPOINT
Orchestrates RTI application filing with Zero-Crash Error Protection.
"""

from fastapi import (
    APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

from config.database import get_db
from config.constants import ApplicationStatus, RTIConstants
from models.rti_application import RTIApplication
from models.audit_log import AuditLog
from models.user import User
from services.portal_adapters import (
    PortalRouter, ApplicantDetails, RTIRequestDetails
)
from services.tracking_service import TrackingService
from services.notification_service import NotificationService
from services.auth_service import AuthService
from api.middleware.auth_middleware import get_current_user
from api.middleware.rate_limiter import limiter
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/filing", tags=["RTI Filing on Portal"])


class FilingSubmitRequest(BaseModel):
    tracking_number: str
    gender: str = "male"
    education: str = "graduate"
    area_type: str = "urban"
    is_life_liberty: bool = False
    consent_to_file: bool = False
    modified_rti_text: Optional[str] = None

    @field_validator("consent_to_file")
    @classmethod
    def must_consent(cls, v):
        if not v:
            raise ValueError("Consent required to file on your behalf.")
        return v


class FilingSubmitResponse(BaseModel):
    tracking_number: str
    status: str
    portal_registration_number: Optional[str] = None
    payment_required: bool = False
    payment_url: Optional[str] = None
    payment_amount: float = 0.0
    message: str
    steps_completed: List[str]
    screenshots_count: int = 0
    response_due_date: Optional[str] = None


class PaymentConfirmRequest(BaseModel):
    tracking_number: str
    transaction_id: Optional[str] = None


class StatusCheckRequest(BaseModel):
    tracking_number: str


class StatusCheckResponse(BaseModel):
    tracking_number: str
    portal_registration_number: Optional[str]
    portal_status: Optional[str]
    portal_status_details: Optional[Dict[str, Any]]
    our_status: str
    message: str


@router.post("/submit", response_model=FilingSubmitResponse)
@limiter.limit("10/hour")
async def submit_rti_to_portal(
    request: Request,
    data: FilingSubmitRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Submit RTI application to government portal.
    Uses PortalRouter with automatic fallback so it NEVER crashes with 502/500 errors.
    """
    result = await db.execute(
        select(RTIApplication).where(
            RTIApplication.tracking_number == data.tracking_number,
            RTIApplication.user_id == user.id,
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )

    auth_service = AuthService(db)
    user_name = auth_service.get_user_display_name(user)
    user_address = auth_service.get_user_address_for_filing(user)

    if not user_name or len(user_name.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your profile name is required for filing."
        )

    if not user_address or len(user_address.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Complete address is required for RTI filing."
        )

    application.status = ApplicationStatus.FILING_IN_PROGRESS
    await db.flush()

    # Log audit
    audit = AuditLog(
        user_id=user.id,
        action="rti_filing_initiated",
        resource_type="rti_application",
        resource_id=application.id,
        details={"tracking_number": data.tracking_number, "consent": True},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(audit)

    rti_text = data.modified_rti_text or application.generated_body

    applicant_details = ApplicantDetails(
        name=user_name,
        gender=data.gender,
        address=user_address,
        pincode=user.pincode or application.issue_pincode or "",
        state=application.issue_state or user.state or "Gujarat",
        city=application.issue_city or user.city or "Ahmedabad",
        district=user.district or "",
        phone=user.phone or "",
        email=user.email,
        education=data.education,
        is_bpl=user.is_bpl,
        area_type=data.area_type,
        is_life_liberty=data.is_life_liberty,
    )

    rti_request_details = RTIRequestDetails(
        department_type=application.department_type.value if application.department_type else "general",
        department_name=application.department_name or "Municipal Corporation",
        public_authority=application.department_name or "",
        rti_text=rti_text,
    )

    # Use Smart Fallback Filing
    portal_router = PortalRouter()
    
    try:
        filing_result = await portal_router.file_with_fallback(
            applicant=applicant_details,
            rti_request=rti_request_details,
        )

        if filing_result.success:
            reg_number = filing_result.registration_number
            payment_url = filing_result.payment_url

            if reg_number:
                application.status = ApplicationStatus.FILED_SUCCESSFULLY
                application.portal_reference_number = reg_number
                application.portal_name = filing_result.portal_name
                application.filing_date = datetime.now(timezone.utc)
                application.fee_paid = user.is_bpl
                application.response_due_date = (
                    datetime.now(timezone.utc) + timedelta(days=RTIConstants.RTI_RESPONSE_DAYS)
                )

                response_due = application.response_due_date.strftime("%d/%m/%Y")

                return FilingSubmitResponse(
                    tracking_number=data.tracking_number,
                    status="filed_successfully",
                    portal_registration_number=reg_number,
                    payment_required=False,
                    payment_url=None,
                    payment_amount=0 if user.is_bpl else 10.0,
                    message=filing_result.message or f"RTI filed! Reg No: {reg_number}",
                    steps_completed=filing_result.steps_completed,
                    screenshots_count=len(filing_result.screenshots),
                    response_due_date=response_due,
                )

            elif payment_url or filing_result.requires_payment:
                application.status = ApplicationStatus.FILING_IN_PROGRESS

                return FilingSubmitResponse(
                    tracking_number=data.tracking_number,
                    status="payment_required",
                    portal_registration_number=None,
                    payment_required=True,
                    payment_url=payment_url or "https://rtionline.gov.in/request/request.php",
                    payment_amount=10.0,
                    message=filing_result.message or "Form submitted on portal. Please complete ₹10 payment.",
                    steps_completed=filing_result.steps_completed,
                    screenshots_count=len(filing_result.screenshots),
                )

            else:
                application.status = ApplicationStatus.FILING_IN_PROGRESS

                return FilingSubmitResponse(
                    tracking_number=data.tracking_number,
                    status="submitted_awaiting_confirmation",
                    portal_registration_number=None,
                    payment_required=not user.is_bpl,
                    payment_url="https://rtionline.gov.in/request/request.php",
                    payment_amount=0 if user.is_bpl else 10.0,
                    message=filing_result.message or "Form submitted. Check email for confirmation.",
                    steps_completed=filing_result.steps_completed,
                    screenshots_count=len(filing_result.screenshots),
                )

        else:
            # Graceful non-crashing response even if all government portals are down
            application.status = ApplicationStatus.FILING_FAILED
            return FilingSubmitResponse(
                tracking_number=data.tracking_number,
                status="portal_temporarily_offline",
                portal_registration_number=None,
                payment_required=False,
                payment_url="https://rtionline.gov.in",
                payment_amount=0,
                message=(
                    f"Government portal was unreachable ({filing_result.error or 'Network Timeout'}). "
                    "You can copy the generated RTI text and submit directly at rtionline.gov.in, or retry in a few minutes."
                ),
                steps_completed=filing_result.steps_completed,
                screenshots_count=0,
            )

    except Exception as e:
        logger.error("filing_exception_safely_handled", tracking_number=data.tracking_number, error=str(e))
        application.status = ApplicationStatus.FILING_FAILED
        return FilingSubmitResponse(
            tracking_number=data.tracking_number,
            status="portal_temporarily_offline",
            portal_registration_number=None,
            payment_required=False,
            payment_url="https://rtionline.gov.in",
            payment_amount=0,
            message="Government website is currently slow or offline. You can retry in a few minutes or submit manually.",
            steps_completed=[],
            screenshots_count=0,
        )
    finally:
        await db.flush()


@router.post("/confirm-payment")
async def confirm_payment(
    data: PaymentConfirmRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(RTIApplication).where(
            RTIApplication.tracking_number == data.tracking_number,
            RTIApplication.user_id == user.id,
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    application.fee_paid = True
    if data.transaction_id:
        application.fee_transaction_id = data.transaction_id

    await db.flush()

    return {
        "tracking_number": data.tracking_number,
        "status": "payment_confirmed",
        "message": "Payment confirmed. Portal will send Registration Number to your email.",
    }


@router.post("/update-registration")
async def update_registration_number(
    tracking_number: str,
    registration_number: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(RTIApplication).where(
            RTIApplication.tracking_number == tracking_number,
            RTIApplication.user_id == user.id,
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    application.portal_reference_number = registration_number
    application.status = ApplicationStatus.FILED_SUCCESSFULLY
    application.filing_date = application.filing_date or datetime.now(timezone.utc)
    application.response_due_date = application.filing_date + timedelta(days=RTIConstants.RTI_RESPONSE_DAYS)

    await db.flush()

    return {
        "tracking_number": tracking_number,
        "portal_registration_number": registration_number,
        "status": "filed_successfully",
        "response_due_date": application.response_due_date.strftime("%d/%m/%Y"),
        "message": f"Registration Number {registration_number} updated successfully.",
    }


@router.post("/check-portal-status", response_model=StatusCheckResponse)
async def check_portal_status(
    data: StatusCheckRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(RTIApplication).where(
            RTIApplication.tracking_number == data.tracking_number,
            RTIApplication.user_id == user.id,
        )
    )
    application = result.scalar_one_or_none()

    if not application or not application.portal_reference_number:
        raise HTTPException(status_code=400, detail="No portal registration number found.")

    portal_router = PortalRouter()
    adapter = portal_router.get_adapter(
        state=application.issue_state or "Gujarat",
        department_type=application.department_type.value if application.department_type else "general",
    )

    portal_result = await adapter.check_status(
        registration_number=application.portal_reference_number,
        email=user.email,
    )

    if portal_result.success:
        return StatusCheckResponse(
            tracking_number=data.tracking_number,
            portal_registration_number=application.portal_reference_number,
            portal_status=portal_result.status,
            portal_status_details={"raw": portal_result.raw_text},
            our_status=application.status.value,
            message=f"Portal status: {portal_result.status}",
        )
    else:
        return StatusCheckResponse(
            tracking_number=data.tracking_number,
            portal_registration_number=application.portal_reference_number,
            portal_status=None,
            portal_status_details=None,
            our_status=application.status.value,
            message="Could not check status on portal.",
        )