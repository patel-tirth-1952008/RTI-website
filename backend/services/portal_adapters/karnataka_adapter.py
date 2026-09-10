# backend/services/portal_adapters/karnataka_adapter.py

from .base_adapter import BasePortalAdapter, FilingResult, StatusResult
from typing import Dict

class KarnatakaPortalAdapter(BasePortalAdapter):
    def __init__(self):
        super().__init__()
        self.portal_name = "Karnataka RTI Portal"
        self.portal_url = "https://rti.karnataka.gov.in"
        self.submit_url = "https://rti.karnataka.gov.in/request"
        self.status_url = "https://rti.karnataka.gov.in/status"

    def supports_state(self, state: str) -> bool:
        return state.lower().strip() in ["karnataka", "ka"]

    def get_department_options(self, department_type, city=""):
        mapping = {
            "municipal_corporation": {
                "bengaluru": {
                    "department": "Urban Development Department",
                    "authority": "BBMP",
                },
                "default": {
                    "department": "Urban Development Department",
                    "authority": "Directorate of Municipal Administration",
                },
            },
        }
        dept = mapping.get(department_type, {"default": {
            "department": "Personnel and Administrative Reforms",
            "authority": "DPAR",
        }})
        return dept.get(city.lower(), dept.get("default", {}))

    async def file_rti(self, applicant, rti_request, page=None):
        return FilingResult(
            success=False,
            error="Karnataka adapter follows same pattern",
            portal_name=self.portal_name,
        )

    async def check_status(self, registration_number, email, page=None):
        return StatusResult(success=False, error="Not yet implemented")