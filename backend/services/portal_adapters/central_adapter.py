"""
CENTRAL GOVERNMENT RTI PORTAL ADAPTER (Thread-Safe Sync Engine)
Portal: https://rtionline.gov.in
"""

import asyncio
from typing import Dict, Any
from .base_adapter import (
    BasePortalAdapter, FilingResult, StatusResult,
    ApplicantDetails, RTIRequestDetails, FilingStep,
)
from services.rti_filing_service import RTIFilingService
import structlog

logger = structlog.get_logger()


class CentralPortalAdapter(BasePortalAdapter):
    """Adapter for Central Government RTI Portal (rtionline.gov.in)."""

    def __init__(self):
        super().__init__()
        self.portal_name = "Central Government RTI Portal"
        self.portal_url = "https://rtionline.gov.in"
        self.submit_url = "https://rtionline.gov.in/request/request.php"
        self.status_url = "https://rtionline.gov.in/request/status.php"
        self.max_text_length = 3000

    def supports_central(self) -> bool:
        return True

    def supports_state(self, state: str) -> bool:
        return False

    def get_department_options(self, department_type: str, city: str = "") -> Dict[str, str]:
        return {
            "department": department_type.replace("_", " ").title(),
            "authority": department_type.replace("_", " ").title(),
        }

    async def file_rti(
        self,
        applicant: ApplicantDetails,
        rti_request: RTIRequestDetails,
        page=None,
    ) -> FilingResult:
        """Delegates central filing to RTIFilingService thread-safe engine."""
        filing_service = RTIFilingService()

        try:
            res = await filing_service.file_on_central_portal(
                applicant_name=applicant.name,
                applicant_gender=applicant.gender,
                applicant_address=applicant.address,
                applicant_pincode=applicant.pincode,
                applicant_state=applicant.state,
                applicant_phone=applicant.phone,
                applicant_email=applicant.email,
                applicant_education=applicant.education,
                is_bpl=applicant.is_bpl,
                is_life_liberty=applicant.is_life_liberty,
                department_type=rti_request.department_type,
                rti_text=rti_request.rti_text,
                supporting_doc_path=rti_request.supporting_doc_path,
                area_type=applicant.area_type,
            )

            return FilingResult(
                success=res.get("success", False),
                registration_number=res.get("registration_number"),
                payment_url=res.get("payment_url"),
                payment_amount=res.get("payment_amount", 10.0),
                requires_payment=res.get("requires_payment", False),
                requires_manual_captcha=res.get("requires_manual_captcha", False),
                captcha_image_base64=res.get("captcha_image"),
                screenshots=res.get("screenshots", []),
                steps_completed=res.get("steps_completed", []),
                error=res.get("error"),
                message=res.get("message"),
                portal_name=self.portal_name,
                portal_url=self.portal_url,
            )

        except Exception as e:
            logger.error("central_adapter_error", error=str(e))
            return FilingResult(
                success=False,
                error=f"Central portal error: {str(e)}",
                portal_name=self.portal_name,
            )

    async def check_status(
        self, registration_number: str, email: str, page=None
    ) -> StatusResult:
        filing_service = RTIFilingService()
        try:
            res = await filing_service.check_status_on_portal(registration_number, email)
            status_details = res.get("status_details", {})
            return StatusResult(
                success=res.get("success", False),
                registration_number=registration_number,
                status=status_details.get("status", "unknown"),
                error=res.get("error"),
            )
        except Exception as e:
            return StatusResult(success=False, error=str(e))