"""
PORTAL ROUTER - Strict Jurisdiction Routing
State issues go ONLY to state portals.
Central issues go ONLY to central portal.
No cross-jurisdiction fallback.
"""

from typing import Dict, Any
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
    """Routes RTI to the correct portal based on state + department type."""

    def __init__(self):
        self._central = CentralPortalAdapter()
        self._gujarat = GujaratPortalAdapter()

        # Map state name -> adapter factory
        self._state_adapters = {
            "gujarat": self._gujarat,
            "gj": self._gujarat,
        }

        # Official portal URLs for user-facing messages
                self._portal_urls = {
            "gujarat": "https://onlinerti.gujarat.gov.in/rti_portal/",
            "gj": "https://onlinerti.gujarat.gov.in/rti_portal/",
            "maharashtra": "https://rtionline.maharashtra.gov.in",
            "delhi": "https://rti.delhi.gov.in",
            "karnataka": "https://rti.karnataka.gov.in",
            "uttar_pradesh": "https://rtionline.up.gov.in",
            "rajasthan": "https://rti.rajasthan.gov.in",
            "tamil_nadu": "https://rtiportal.tn.gov.in",
            "central": "https://rtionline.gov.in",
        }

    def get_adapter(
        self,
        state: str,
        department_type: str,
        department_name: str = "",
    ) -> BasePortalAdapter:
        """
        STRICT RULES:
        1. Central subjects (NHAI, Railways, Passport, etc.) -> Central only
        2. State subjects -> That state's portal only
        3. Never send AMC/state issues to central portal
        """
        state_clean = (state or "").lower().strip().replace(" ", "_")

        # 1. Central jurisdiction only
        if self._is_central_subject(department_type, department_name):
            logger.info(
                "routing_to_central_only",
                reason="central_subject",
                dept_type=department_type,
            )
            return self._central

        # 2. Known state adapter (e.g. Gujarat)
        if state_clean in self._state_adapters:
            adapter = self._state_adapters[state_clean]
            logger.info(
                "routing_to_state_portal",
                state=state_clean,
                portal=adapter.portal_name,
            )
            return adapter

        # 3. Other states -> Generic adapter for that state's portal URL
        portal_url = RTI_PORTALS.get(
            state_clean,
            self._portal_urls.get(state_clean, "https://rtionline.gov.in"),
        )
        # If no state portal known, still do NOT force central for municipal issues
        if department_type in (
            "municipal_corporation", "pwd", "water_board",
            "electricity_board", "panchayat", "education_department",
            "health_department", "police_department", "revenue_department",
        ):
            logger.info(
                "routing_to_generic_state_portal",
                state=state_clean,
                portal_url=portal_url,
            )
            return GenericAIAdapter(
                portal_url=portal_url,
                portal_name=f"{(state or 'State').title()} RTI Portal",
            )

        # 4. Unknown general -> central only if truly general/central
        logger.info("routing_to_central_general", state=state_clean)
        return self._central

    def get_portal_url_for_user(self, state: str, department_type: str, department_name: str = "") -> str:
        """Return the official URL users should open manually if auto-file fails."""
        adapter = self.get_adapter(state, department_type, department_name)
        return getattr(adapter, "portal_url", None) or getattr(adapter, "submit_url", None) or "https://rtionline.gov.in"

    async def file_with_strict_jurisdiction(
        self,
        applicant: ApplicantDetails,
        rti_request: RTIRequestDetails,
    ) -> FilingResult:
        """
        File ONLY on the correct jurisdiction portal.
        No fallback from state -> central for municipal/state issues.
        """
        adapter = self.get_adapter(
            state=applicant.state,
            department_type=rti_request.department_type,
            department_name=rti_request.department_name,
        )

        portal_url = (
            getattr(adapter, "submit_url", None)
            or getattr(adapter, "portal_url", None)
            or "https://rtionline.gov.in"
        )

        logger.info(
            "strict_filing_start",
            portal=adapter.portal_name,
            url=portal_url,
            state=applicant.state,
            city=applicant.city,
            dept=rti_request.department_type,
        )

        try:
            result = await adapter.file_rti(applicant, rti_request)

            # Always attach correct portal info for frontend
            if not result.portal_name:
                result.portal_name = adapter.portal_name
            if not result.portal_url:
                result.portal_url = portal_url

            if not result.success:
                # Friendly message with CORRECT portal link
                err = result.error or "Portal unreachable or timed out"
                result.message = (
                    f"The {adapter.portal_name} could not be reached right now "
                    f"({err}). "
                    f"Your RTI draft is saved. "
                    f"You can copy the draft and submit manually at: {portal_url} "
                    f"— or retry auto-filing in a few minutes."
                )
                # Put correct manual URL in payment_url field so UI button opens right site
                if not result.payment_url:
                    result.payment_url = portal_url

            return result

        except Exception as e:
            logger.error(
                "strict_filing_exception",
                portal=adapter.portal_name,
                error=str(e),
            )
            return FilingResult(
                success=False,
                error=str(e),
                portal_name=adapter.portal_name,
                portal_url=portal_url,
                payment_url=portal_url,
                message=(
                    f"Could not reach {adapter.portal_name}. "
                    f"Please submit manually at {portal_url} using your saved draft, "
                    f"or retry later."
                ),
            )

    def _is_central_subject(self, department_type: str, department_name: str) -> bool:
        """Only true central government subjects."""
        type_lower = (department_type or "").lower()
        name_lower = (department_name or "").lower()

        if type_lower == "nhai":
            return True

        central_keywords = [
            "nhai", "national highway", "railway", "indian railways",
            "passport", "immigration", "income tax", "customs",
            "defence", "cantonment", "ministry of external",
            "ministry of defence", "central government",
        ]
        return any(kw in name_lower for kw in central_keywords)