import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from config.settings import settings
from config.constants import DepartmentType, IssueCategory
import structlog

logger = structlog.get_logger()


class DepartmentResolverService:
    """
    Resolves which government department to file RTI with,
    based on issue type, location, and other factors.
    """

    def __init__(self):
        try:
            self.geolocator = Nominatim(
                user_agent=settings.NOMINATIM_USER_AGENT,
                timeout=5
            )
        except Exception:
            self.geolocator = None

        self._departments_data = self._load_departments_data()
        self._pio_directory = self._load_pio_directory()

    def _load_departments_data(self) -> Dict:
        """Load department mapping data safely."""
        data_file = settings.BASE_DIR / "data" / "departments.json"
        if data_file.exists():
            try:
                with open(data_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        return json.loads(content)
            except Exception as e:
                logger.warning("failed_to_load_departments_json", error=str(e))

        # Default fallback department mappings
        return {
            "category_to_department": {
                "road_repair": {
                    "default": "municipal_corporation",
                    "state_highway": "pwd",
                    "national_highway": "nhai",
                    "rural": "panchayat",
                    "cantonment": "cantonment_board",
                },
                "water_supply": {
                    "default": "water_board",
                    "rural": "panchayat",
                },
                "electricity": {
                    "default": "electricity_board",
                },
                "sanitation": {
                    "default": "municipal_corporation",
                    "rural": "panchayat",
                },
                "education": {
                    "default": "education_department",
                },
                "healthcare": {
                    "default": "health_department",
                },
                "police": {
                    "default": "police_department",
                },
                "land_records": {
                    "default": "revenue_department",
                },
            },
            "state_departments": {
                "gujarat": {
                    "municipal_corporation": {
                        "ahmedabad": "Ahmedabad Municipal Corporation (AMC)",
                        "surat": "Surat Municipal Corporation (SMC)",
                        "vadodara": "Vadodara Municipal Corporation (VMC)",
                        "default": "Municipal Corporation",
                    },
                    "pwd": "Gujarat Roads and Buildings Department (PWD)",
                    "water_board": "Gujarat Water Supply and Sewerage Board",
                    "electricity_board": "Gujarat Urja Vikas Nigam Limited (GUVNL)",
                },
                "maharashtra": {
                    "municipal_corporation": {
                        "mumbai": "Brihanmumbai Municipal Corporation (BMC)",
                        "pune": "Pune Municipal Corporation (PMC)",
                        "default": "Municipal Corporation",
                    },
                    "pwd": "Maharashtra Public Works Department",
                },
                "delhi": {
                    "municipal_corporation": {
                        "default": "Municipal Corporation of Delhi (MCD)",
                    },
                    "pwd": "Delhi Public Works Department",
                    "water_board": "Delhi Jal Board",
                },
            },
        }

    def _load_pio_directory(self) -> Dict:
        """Load PIO directory safely."""
        data_file = settings.BASE_DIR / "data" / "pio_directory.json"
        if data_file.exists():
            try:
                with open(data_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        return json.loads(content)
            except Exception as e:
                logger.warning("failed_to_load_pio_directory_json", error=str(e))
        return {}

    async def resolve_department(
        self,
        category: str,
        state: str,
        city: str = None,
        district: str = None,
        latitude: float = None,
        longitude: float = None,
        road_type: str = None,
        area_type: str = None,
    ) -> Dict[str, Any]:
        """Resolve correct department, PIO, and address."""
        try:
            state = state.lower().strip() if state else "gujarat"
            city = city.lower().strip() if city else "ahmedabad"

            dept_mapping = self._departments_data.get(
                "category_to_department", {}
            ).get(category, {})

            if road_type == "national_highway":
                dept_type = "nhai"
            elif road_type == "state_highway":
                dept_type = "pwd"
            elif area_type == "rural":
                dept_type = dept_mapping.get("rural", dept_mapping.get("default", "general"))
            else:
                dept_type = dept_mapping.get("default", "general")

            state_depts = self._departments_data.get(
                "state_departments", {}
            ).get(state, {})

            dept_info = state_depts.get(dept_type, {})
            if isinstance(dept_info, dict):
                dept_name = dept_info.get(city, dept_info.get("default", ""))
            elif isinstance(dept_info, str):
                dept_name = dept_info
            else:
                dept_name = dept_type.replace("_", " ").title()

            if not dept_name:
                dept_name = f"{city.title()} {dept_type.replace('_', ' ').title()}"

            pio_info = self._get_pio_info(dept_type, state, city, district)

            from config.constants import RTI_PORTALS
            portal_url = RTI_PORTALS.get(
                state, RTI_PORTALS.get("central", "https://rtionline.gov.in")
            )

            return {
                "department_type": dept_type,
                "department_name": dept_name,
                "pio_name": pio_info.get("name", "The Public Information Officer"),
                "pio_address": pio_info.get("address", f"{dept_name}, {city.title()}, {state.title()}"),
                "pio_email": pio_info.get("email", ""),
                "pio_phone": pio_info.get("phone", ""),
                "portal_url": portal_url,
                "state": state,
                "city": city,
                "confidence": 0.85,
            }

        except Exception as e:
            logger.error("department_resolution_failed", error=str(e))
            return {
                "department_type": "general",
                "department_name": "Public Information Officer",
                "pio_name": "The Public Information Officer",
                "pio_address": f"{city or 'Ahmedabad'}, {state or 'Gujarat'}",
                "portal_url": "https://rti.gujarat.gov.in",
                "confidence": 0.5,
            }

    def _get_pio_info(
        self, dept_type: str, state: str, city: str, district: str = None
    ) -> Dict[str, str]:
        """Look up PIO information."""
        try:
            state_pios = self._pio_directory.get(state, {})
            dept_pios = state_pios.get(dept_type, {})

            if city and city in dept_pios:
                return dept_pios[city]
            if district and district in dept_pios:
                return dept_pios[district]
            if "default" in dept_pios:
                return dept_pios["default"]
        except Exception:
            pass

        return {
            "name": "The Public Information Officer (PIO)",
            "address": f"{dept_type.replace('_', ' ').title()} Office, {city.title() if city else 'Ahmedabad'}",
        }