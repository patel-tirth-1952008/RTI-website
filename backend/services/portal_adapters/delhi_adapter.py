# backend/services/portal_adapters/delhi_adapter.py

from .base_adapter import BasePortalAdapter, FilingResult, StatusResult
from typing import Dict

class DelhiPortalAdapter(BasePortalAdapter):
    def __init__(self):
        super().__init__()
        self.portal_name = "Delhi RTI Portal"
        self.portal_url = "https://rti.delhi.gov.in"
        self.submit_url = "https://rti.delhi.gov.in/request"
        self.status_url = "https://rti.delhi.gov.in/status"

    def supports_state(self, state: str) -> bool:
        return state.lower().strip() in ["delhi", "dl", "new delhi"]

    def get_department_options(self, department_type, city=""):
        mapping = {
            "municipal_corporation": {
                "default": {
                    "department": "Urban Development",
                    "authority": "Municipal Corporation of Delhi (MCD)",
                },
            },
            "pwd": {
                "default": {
                    "department": "Public Works Department",
                    "authority": "PWD Delhi",
                },
            },
            "water_board": {
                "default": {
                    "department": "Water",
                    "authority": "Delhi Jal Board",
                },
            },
        }
        dept = mapping.get(department_type, {"default": {
            "department": "General Administration",
            "authority": "Govt of NCT of Delhi",
        }})
        return dept.get("default", {})

    async def file_rti(self, applicant, rti_request, page=None):
        return FilingResult(
            success=False,
            error="Delhi adapter follows same pattern",
            portal_name=self.portal_name,
        )

    async def check_status(self, registration_number, email, page=None):
        return StatusResult(success=False, error="Not yet implemented")