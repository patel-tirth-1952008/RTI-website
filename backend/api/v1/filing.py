"""
RTI FILING API ENDPOINT
Strict jurisdiction routing + Zero-Crash Error Protection.
Gujarat/AMC issues go ONLY to rti.gujarat.gov.in
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
    steps_completed: List[str] = []
    screenshots_count: int = 0
    response_due_date: Optional[str] = None


class PaymentConfirmRequest(BaseModel):
    tracking_number: str
    transaction_id: Optional[str] = None


class StatusCheckRequest(BaseModel):
    tracking_number: str


class StatusCheckResponse(BaseModel):
    tracking_number: str
    portal_registration_number: Optional[str] = None
    portal_status: Optional[str] = None
    portal_status_details: Optional[Dict[str, Any]] = None
    our_status: str
    message: str


def _default_portal_url(state: str, department_type: str) -> str:
    """Return correct official portal URL for manual filing."""
    state_l = (state or "").lower().strip()
    dept_l = (department_type or "").lower().strip()

    central_depts = {"nhai", "railway", "passport", "income_tax", "defence"}
    if dept_l in central_depts or "nhai" in dept_l:
        return "https://rtionline.gov.in"

    state_urls = {
        "gujarat": "https://rti.gujarat.gov.in",
        "gj": "https://rti.gujarat.gov.in",
        "maharashtra": "https://rtionline.maharashtra.gov.in",
        "delhi": "https://rti.delhi.gov.in",
        "karnataka": "https://rti.karnataka.gov.in",
        "uttar_pradesh": "https://rtionline.up.gov.in",
        "up": "https://rtionline.up.gov.in",
        "rajasthan": "https://rti.rajasthan.gov.in",
        "tamil_nadu": "https://rtiportal.tn.gov.in",
        "tamilnadu": "https://rtiportal.tn.gov.in",
    }
    return state_urls.get(state_l, "https://rti.gujarat.gov.in")


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
    Submit RTI to the CORRECT jurisdiction portal only.
    Gujarat/AMC -> rti.gujarat.gov.in ONLY
    NHAI/Railways -> rtionline.gov.in ONLY
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

    rti_text = data.modified_rti_text or application.generated_body or ""

    issue_state = application.issue_state or user.state or "Gujarat"
    issue_city = application.issue_city or user.city or "Ahmedabad"
    dept_type = (
        application.department_type.value
        if application.department_type
        else "municipal_corporation"
    )

    applicant_details = ApplicantDetails(
        name=user_name,
        gender=data.gender,
        address=user_address,
        pincode=user.pincode or application.issue_pincode or "",
        state=issue_state,
        city=issue_city,
        district=user.district or "",
        phone=user.phone or "",
        email=user.email,
        education=data.education,
        is_bpl=user.is_bpl,
        area_type=data.area_type,
        is_life_liberty=data.is_life_liberty,
    )

    rti_request_details = RTIRequestDetails(
        department_type=dept_type,
        department_name=application.department_name or "Municipal Corporation",
        public_authority=application.department_name or "",
        rti_text=rti_text,
    )

    correct_portal_url = _default_portal_url(issue_state, dept_type)
    portal_router = PortalRouter()

    try:
        # STRICT jurisdiction: state issues stay on state portal
        if hasattr(portal_router, "file_with_strict_jurisdiction"):
            filing_result = await portal_router.file_with_strict_jurisdiction(
                applicant=applicant_details,
                rti_request=rti_request_details,
            )
        else:
            # Fallback if old router method name still exists
            adapter = portal_router.get_adapter(
                state=issue_state,
                department_type=dept_type,
                department_name=application.department_name or "",
            )
            filing_result = await adapter.file_rti(
                applicant=applicant_details,
                rti_request=rti_request_details,
            )

        portal_name = getattr(filing_result, "portal_name", None) or "State RTI Portal"
        portal_url = (
            getattr(filing_result, "portal_url", None)
            or getattr(filing_result, "payment_url", None)
            or correct_portal_url
        )

        if filing_result.success:
            reg_number = filing_result.registration_number
            payment_url = filing_result.payment_url

            if reg_number:
                application.status = ApplicationStatus.FILED_SUCCESSFULLY
                application.portal_reference_number = reg_number
                application.portal_name = portal_name
                application.filing_date = datetime.now(timezone.utc)
                application.fee_paid = bool(user.is_bpl)
                application.response_due_date = (
                    datetime.now(timezone.utc)
                    + timedelta(days=RTIConstants.RTI_RESPONSE_DAYS)
                )
                response_due = application.response_due_date.strftime("%d/%m/%Y")

                return FilingSubmitResponse(
                    tracking_number=data.tracking_number,
                    status="filed_successfully",
                    portal_registration_number=reg_number,
                    payment_required=False,
                    payment_url=None,
                    payment_amount=0 if user.is_bpl else 10.0,
                    message=filing_result.message or f"RTI filed on {portal_name}! Reg No: {reg_number}",
                    steps_completed=filing_result.steps_completed or [],
                    screenshots_count=len(filing_result.screenshots or []),
                    response_due_date=response_due,
                )

            if payment_url or filing_result.requires_payment:
                application.status = ApplicationStatus.FILING_IN_PROGRESS
                application.portal_name = portal_name

                return FilingSubmitResponse(
                    tracking_number=data.tracking_number,
                    status="payment_required",
                    portal_registration_number=None,
                    payment_required=True,
                    payment_url=payment_url or portal_url,
                    payment_amount=10.0,
                    message=(
                        filing_result.message
                        or f"Form submitted on {portal_name}. Please complete ₹10 payment on the official portal."
                    ),
                    steps_completed=filing_result.steps_completed or [],
                    screenshots_count=len(filing_result.screenshots or []),
                )

            application.status = ApplicationStatus.FILING_IN_PROGRESS
            return FilingSubmitResponse(
                tracking_number=data.tracking_number,
                status="submitted_awaiting_confirmation",
                portal_registration_number=None,
                payment_required=not user.is_bpl,
                payment_url=portal_url,
                payment_amount=0 if user.is_bpl else 10.0,
                message=(
                    filing_result.message
                    or f"Form submitted on {portal_name}. Check your email for confirmation."
                ),
                steps_completed=filing_result.steps_completed or [],
                screenshots_count=len(filing_result.screenshots or []),
            )

        # Failed - still return correct state portal link (NOT always central)
        application.status = ApplicationStatus.FILING_FAILED
        err = filing_result.error or "Network Timeout"
        return FilingSubmitResponse(
            tracking_number=data.tracking_number,
            status="portal_temporarily_offline",
            portal_registration_number=None,
            payment_required=not user.is_bpl,
            payment_url=portal_url,
            payment_amount=0 if user.is_bpl else 10.0,
            message=(
                filing_result.message
                or (
                    f"{portal_name} could not be reached ({err}). "
                    f"Your draft is saved. Open {portal_url} and paste your draft, "
                    f"or retry auto-filing in a few minutes."
                )
            ),
            steps_completed=filing_result.steps_completed or [],
            screenshots_count=0,
        )

    except Exception as e:
        logger.error(
            "filing_exception_safely_handled",
            tracking_number=data.tracking_number,
            error=str(e),
        )
        application.status = ApplicationStatus.FILING_FAILED
        return FilingSubmitResponse(
            tracking_number=data.tracking_number,
            status="portal_temporarily_offline",
            portal_registration_number=None,
            payment_required=not user.is_bpl,
            payment_url=correct_portal_url,
            payment_amount=0 if user.is_bpl else 10.0,
            message=(
                f"Could not complete auto-filing right now. "
                f"Your draft is saved. Open {correct_portal_url} to submit manually, "
                f"or retry in a few minutes."
            ),
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
    application.response_due_date = application.filing_date + timedelta(
        days=RTIConstants.RTI_RESPONSE_DAYS
    )

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
        raise HTTPException(
            status_code=400,
            detail="No portal registration number found."
        )

    portal_router = PortalRouter()
    adapter = portal_router.get_adapter(
        state=application.issue_state or "Gujarat",
        department_type=(
            application.department_type.value
            if application.department_type
            else "municipal_corporation"
        ),
        department_name=application.department_name or "",
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
            portal_status_details={"raw": getattr(portal_result, "raw_text", None)},
            our_status=application.status.value,
            message=f"Portal status: {portal_result.status}",
        )

    return StatusCheckResponse(
        tracking_number=data.tracking_number,
        portal_registration_number=application.portal_reference_number,
        portal_status=None,
        portal_status_details=None,
        our_status=application.status.value,
        message="Could not check status on portal.",
    )