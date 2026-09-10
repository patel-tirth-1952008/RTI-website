# backend/services/portal_adapters/base_adapter.py

"""
BASE PORTAL ADAPTER
====================
Abstract base class that defines the interface all state portal
adapters must implement.

Every Indian state RTI portal follows the same legal framework
(RTI Act 2005) but has different:
- URLs and page structures
- Form field names and CSS selectors
- Dropdown values (department names)
- CAPTCHA implementations
- Payment gateway integrations
- Registration number formats

This base class standardizes the interface so the rest of our
system doesn't need to know which portal is being used.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import base64


class FilingStep(str, Enum):
    NAVIGATE = "navigate_to_portal"
    GUIDELINES = "accept_guidelines"
    SELECT_DEPT = "select_department"
    SELECT_AUTHORITY = "select_public_authority"
    LIFE_LIBERTY = "answer_life_liberty"
    FILL_NAME = "fill_applicant_name"
    FILL_GENDER = "fill_gender"
    FILL_ADDRESS = "fill_address"
    FILL_PINCODE = "fill_pincode"
    FILL_STATE = "fill_state"
    FILL_URBAN_RURAL = "fill_urban_rural"
    FILL_EDUCATION = "fill_education"
    FILL_PHONE = "fill_phone"
    FILL_EMAIL = "fill_email"
    FILL_CITIZENSHIP = "fill_citizenship"
    FILL_BPL = "fill_bpl_status"
    FILL_TEXT = "fill_rti_text"
    UPLOAD_DOC = "upload_document"
    SOLVE_CAPTCHA = "solve_captcha"
    SUBMIT = "submit_form"
    PAYMENT = "handle_payment"
    CAPTURE_REG = "capture_registration_number"


@dataclass
class FilingResult:
    """Standardized result from any portal adapter."""
    success: bool
    registration_number: Optional[str] = None
    payment_url: Optional[str] = None
    payment_amount: float = 0.0
    requires_payment: bool = False
    requires_manual_captcha: bool = False
    captcha_image_base64: Optional[str] = None
    screenshots: List[str] = field(default_factory=list)
    steps_completed: List[str] = field(default_factory=list)
    error: Optional[str] = None
    message: Optional[str] = None
    portal_name: Optional[str] = None
    portal_url: Optional[str] = None
    raw_page_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "registration_number": self.registration_number,
            "payment_url": self.payment_url,
            "payment_amount": self.payment_amount,
            "requires_payment": self.requires_payment,
            "requires_manual_captcha": self.requires_manual_captcha,
            "screenshots_count": len(self.screenshots),
            "steps_completed": self.steps_completed,
            "error": self.error,
            "message": self.message,
            "portal_name": self.portal_name,
        }


@dataclass
class StatusResult:
    """Standardized result from status check on any portal."""
    success: bool
    registration_number: Optional[str] = None
    status: Optional[str] = None  # pending, response_received, transferred, rejected
    department: Optional[str] = None
    filing_date: Optional[str] = None
    response_date: Optional[str] = None
    response_text: Optional[str] = None
    response_document_url: Optional[str] = None
    error: Optional[str] = None
    raw_text: Optional[str] = None
    screenshot: Optional[str] = None


@dataclass
class ApplicantDetails:
    """Standardized applicant information passed to all adapters."""
    name: str
    gender: str  # "male", "female", "transgender"
    address: str
    pincode: str
    state: str
    city: str
    district: str
    phone: str
    email: str
    education: str  # "graduate", "matric_secondary", etc.
    is_bpl: bool
    bpl_document_path: Optional[str] = None
    area_type: str = "urban"  # "urban" or "rural"
    is_life_liberty: bool = False


@dataclass
class RTIRequestDetails:
    """Standardized RTI request information."""
    department_type: str  # "municipal_corporation", "pwd", etc.
    department_name: str
    public_authority: str
    rti_text: str
    supporting_doc_path: Optional[str] = None
    language: str = "en"


class BasePortalAdapter(ABC):
    """
    Abstract base class for all RTI portal adapters.

    Each state's RTI portal gets its own adapter that knows:
    - The exact URL to navigate to
    - The CSS selectors for every form field
    - The exact dropdown values for departments/authorities
    - How to solve that portal's specific CAPTCHA
    - How to handle that portal's payment flow
    - The registration number format to look for
    """

    def __init__(self):
        self.portal_name: str = "Unknown Portal"
        self.portal_url: str = ""
        self.submit_url: str = ""
        self.status_url: str = ""
        self.max_text_length: int = 3000
        self.supported_file_types: List[str] = [".pdf"]
        self.max_file_size_mb: float = 1.0
        self.registration_number_pattern: str = r"[A-Z0-9/]+"

    @abstractmethod
    async def file_rti(
        self,
        applicant: ApplicantDetails,
        rti_request: RTIRequestDetails,
        page=None,  # Playwright page (injected for testing)
    ) -> FilingResult:
        """
        File an RTI application on this portal.

        This is the main method that:
        1. Opens the portal
        2. Fills all form fields
        3. Solves CAPTCHA
        4. Submits the form
        5. Handles payment redirect
        6. Captures registration number

        Args:
            applicant: Standardized applicant details
            rti_request: Standardized RTI request details
            page: Optional Playwright page for dependency injection

        Returns:
            FilingResult with success status and details
        """
        pass

    @abstractmethod
    async def check_status(
        self,
        registration_number: str,
        email: str,
        page=None,
    ) -> StatusResult:
        """
        Check the status of a filed RTI on this portal.

        Args:
            registration_number: The portal's registration number
            email: The applicant's email address
            page: Optional Playwright page

        Returns:
            StatusResult with current status details
        """
        pass

    @abstractmethod
    def get_department_options(
        self, department_type: str, city: str = ""
    ) -> Dict[str, str]:
        """
        Get the exact dropdown values for this portal.

        Returns:
            {
                "ministry_label": "exact text in dropdown",
                "authority_label": "exact text in dropdown",
                "ministry_value": "option value attribute",
                "authority_value": "option value attribute",
            }
        """
        pass

    def supports_state(self, state: str) -> bool:
        """Check if this adapter handles the given state."""
        return False

    def supports_central(self) -> bool:
        """Check if this adapter handles central government RTIs."""
        return False

    def get_portal_info(self) -> Dict[str, Any]:
        """Get information about this portal."""
        return {
            "name": self.portal_name,
            "url": self.portal_url,
            "submit_url": self.submit_url,
            "status_url": self.status_url,
            "max_text_length": self.max_text_length,
        }