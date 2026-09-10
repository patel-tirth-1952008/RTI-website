"""
PORTAL ROUTER (Smart Fallback Engine)
Determines which portal adapter to use and automatically falls back to
rtionline.gov.in if any state portal is down or unreachable.
"""

from typing import Optional, Dict, Any
from .base_adapter import (
    BasePortalAdapter, FilingResult, StatusResult,
    ApplicantDetails, RTIRequestDetails
)
from .central_adapter import CentralPortalAdapter
from .gujarat_adapter import GujaratPortalAdapter
from .generic_ai_adapter import GenericAIAdapter
from config.constants import RTI_PORTALS
import structlog

logger = structlog.get_logger()


class PortalRouter:
    """Routes RTI applications with automatic fallback protection."""

    def __init__(self):
        self._central = CentralPortalAdapter()
        self._gujarat = GujaratPortalAdapter()

    def get_adapter(
        self,
        state: str,
        department_type: str,
        department_name: str = "",
    ) -> BasePortalAdapter:
        state_clean = (state or "").lower().strip()

        # Central subjects -> Central Portal
        if self._is_central_subject(department_type, department_name):
            logger.info("routing_to_central_portal", dept_type=department_type)
            return self._central

        # Gujarat state -> Gujarat Portal Adapter
        if self._gujarat.supports_state(state_clean):
            logger.info("routing_to_gujarat_portal", state=state_clean)
            return self._gujarat

        # Other states -> Generic AI Adapter
        portal_url = RTI_PORTALS.get(
            state_clean.replace(" ", "_"),
            "https://rtionline.gov.in"
        )
        logger.info("routing_to_generic_ai_adapter", state=state_clean, portal_url=portal_url)
        return GenericAIAdapter(
            portal_url=portal_url,
            portal_name=f"{state.title() if state else 'State'} RTI Portal"
        )

    async def file_with_fallback(
        self,
        applicant: ApplicantDetails,
        rti_request: RTIRequestDetails,
    ) -> FilingResult:
        """
        Tries primary state adapter.
        If state portal is down/unreachable -> automatically files on rtionline.gov.in!
        """
        adapter = self.get_adapter(
            state=applicant.state,
            department_type=rti_request.department_type,
            department_name=rti_request.department_name,
        )

        try:
            result = await adapter.file_rti(applicant, rti_request)
            if result.success:
                return result

            # If primary adapter failed due to network/DNS error, fall back to Central Portal
            if "ERR_NAME_NOT_RESOLVED" in str(result.error) or "net::" in str(result.error) or "timeout" in str(result.error).lower():
                logger.warning("state_portal_unreachable_falling_back_to_central", error=result.error)
                fallback_result = await self._central.file_rti(applicant, rti_request)
                fallback_result.message = f"(Filed via Central Portal because {adapter.portal_name} was offline) " + (fallback_result.message or "")
                return fallback_result

            return result

        except Exception as e:
            logger.warning("primary_adapter_failed_falling_back_to_central", error=str(e))
            try:
                fallback_result = await self._central.file_rti(applicant, rti_request)
                fallback_result.message = f"(Filed via Central Portal - fallback) " + (fallback_result.message or "")
                return fallback_result
            except Exception as e2:
                return FilingResult(
                    success=False,
                    error=f"Both primary and central portals were unreachable. Please try again later.",
                    portal_name="Central Government RTI Portal",
                )

    def _is_central_subject(self, department_type: str, department_name: str) -> bool:
        central_keywords = [
            "nhai", "national highway", "railway", "defence",
            "cantonment", "passport", "immigration", "income tax",
            "customs", "central", "ministry of external",
            "ministry of defence", "indian railways"
        ]
        dept_lower = (department_name or "").lower()
        type_lower = (department_type or "").lower()

        if type_lower == "nhai":
            return True

        return any(kw in dept_lower for kw in central_keywords)