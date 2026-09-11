# backend/config/constants.py

from enum import Enum
from typing import Dict, List


class RTIConstants:
    """All constants for the RTI Filing System."""

    RTI_FEE_INR = 10
    RTI_RESPONSE_DAYS = 30
    RTI_LIFE_LIBERTY_HOURS = 48
    FIRST_APPEAL_DAYS = 30
    SECOND_APPEAL_DAYS = 90

    # Supported languages
    SUPPORTED_LANGUAGES = ["en", "hi", "mr", "ta", "te", "kn", "bn", "gu", "ml"]


class ApplicationStatus(str, Enum):
    DRAFT = "draft"
    GENERATED = "generated"
    REVIEW_PENDING = "review_pending"
    FILING_IN_PROGRESS = "filing_in_progress"
    FILED_SUCCESSFULLY = "filed_successfully"
    FILING_FAILED = "filing_failed"
    RESPONSE_RECEIVED = "response_received"
    FIRST_APPEAL = "first_appeal"
    SECOND_APPEAL = "second_appeal"
    CLOSED = "closed"


class IssueCategory(str, Enum):
    ROAD_REPAIR = "road_repair"
    WATER_SUPPLY = "water_supply"
    ELECTRICITY = "electricity"
    SANITATION = "sanitation"
    EDUCATION = "education"
    HEALTHCARE = "healthcare"
    CORRUPTION = "corruption"
    GOVERNMENT_SCHEME = "government_scheme"
    LAND_RECORDS = "land_records"
    POLICE = "police"
    ENVIRONMENT = "environment"
    PUBLIC_TRANSPORT = "public_transport"
    GENERAL = "general"


class DepartmentType(str, Enum):
    MUNICIPAL_CORPORATION = "municipal_corporation"
    PWD = "pwd"
    NHAI = "nhai"
    WATER_BOARD = "water_board"
    ELECTRICITY_BOARD = "electricity_board"
    EDUCATION_DEPARTMENT = "education_department"
    HEALTH_DEPARTMENT = "health_department"
    POLICE_DEPARTMENT = "police_department"
    REVENUE_DEPARTMENT = "revenue_department"
    PANCHAYAT = "panchayat"
    CANTONMENT_BOARD = "cantonment_board"
    GENERAL = "general"


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    API_CLIENT = "api_client"


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"


class FraudCheckResult(str, Enum):
    AUTHENTIC = "authentic"
    SUSPICIOUS = "suspicious"
    AI_GENERATED = "ai_generated"
    MANIPULATED = "manipulated"
    METADATA_MISSING = "metadata_missing"
    INCONCLUSIVE = "inconclusive"


# State-wise RTI portal URLs
RTI_PORTALS: Dict[str, str] = {
    "central": "https://rtionline.gov.in",
    "delhi": "https://rti.delhi.gov.in",
    "maharashtra": "https://rtionline.maharashtra.gov.in",
    "karnataka": "https://rti.karnataka.gov.in",
    "tamil_nadu": "https://rtiportal.tn.gov.in",
    "uttar_pradesh": "https://rtionline.up.gov.in",
    "rajasthan": "https://rti.rajasthan.gov.in",
    "madhya_pradesh": "https://rtimp.gov.in",
    "gujarat": "https://onlinerti.gujarat.gov.in/rti_portal/",
    "west_bengal": "https://rtionline.wb.gov.in",
    "andhra_pradesh": "https://rti.ap.gov.in",
    "telangana": "https://rti.telangana.gov.in",
    "kerala": "https://sic.kerala.gov.in",
    "punjab": "https://rti.punjab.gov.in",
    "haryana": "https://rtionline.haryana.gov.in",
    "bihar": "https://rti.bihar.gov.in",
}

# Department keywords for auto-detection
DEPARTMENT_KEYWORDS: Dict[str, List[str]] = {
    "road_repair": [
        "road", "pothole", "broken road", "highway", "flyover",
        "bridge", "footpath", "pavement", "street", "lane",
        "sadak", "sarak", "rasta", "marg"
    ],
    "water_supply": [
        "water", "pipe", "leak", "drainage", "sewer", "borewell",
        "tanker", "supply", "pani", "jal", "neer"
    ],
    "electricity": [
        "electricity", "power", "transformer", "pole", "wire",
        "meter", "bill", "outage", "bijli", "vidyut"
    ],
    "sanitation": [
        "garbage", "waste", "clean", "sweeper", "dustbin",
        "toilet", "drain", "kachra", "safai", "swachh"
    ],
    "education": [
        "school", "teacher", "student", "education", "college",
        "university", "scholarship", "vidyalaya", "shiksha"
    ],
    "healthcare": [
        "hospital", "doctor", "medicine", "health", "clinic",
        "ambulance", "dispensary", "aspatal", "swasthya"
    ],
}