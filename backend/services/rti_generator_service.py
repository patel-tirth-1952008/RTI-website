# backend/services/rti_generator_service.py

import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.rti_application import RTIApplication
from models.user import User
from schemas.rti import RTICreateRequest, RTIGenerateResponse, RTIAnalysisResult
from services.image_analysis_service import ImageAnalysisService
from services.department_resolver_service import DepartmentResolverService
from services.fraud_detection_service import FraudDetectionService
from config.settings import settings
from config.security import security_manager
from config.constants import (
    ApplicationStatus, IssueCategory, DepartmentType, RTIConstants
)
import structlog

logger = structlog.get_logger()


class RTIGeneratorService:
    """
    Core service that orchestrates RTI application generation.
    Handles:
    1. Issue analysis (AI-powered)
    2. Department resolution
    3. RTI text generation
    4. PDF generation
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.image_analyzer = ImageAnalysisService()
        self.dept_resolver = DepartmentResolverService()
        self.fraud_detector = FraudDetectionService()

    async def create_rti_application(
        self,
        user: User,
        request: RTICreateRequest,
        image_bytes: Optional[bytes] = None,
        image_filename: Optional[str] = None,
    ) -> RTIGenerateResponse:
        """
        Main method to create an RTI application.
        Analyzes the issue, resolves department, generates RTI text.
        """
        # Step 1: Generate tracking number
        tracking_number = self._generate_tracking_number()

        # Step 2: Analyze image if provided
        analysis_result = None
        fraud_result = None

        if image_bytes:
            # Fraud detection first
            fraud_result = await self.fraud_detector.analyze_image(
                image_bytes, image_filename or "image.jpg"
            )

            # Only proceed with AI analysis if image is not flagged as fake
            if fraud_result["overall_result"] not in ["ai_generated"]:
                analysis_result = await self.image_analyzer.analyze_image_for_rti(
                    image_bytes,
                    request.issue_description,
                    request.issue_location,
                    request.language,
                )

        # Step 3: Determine category
        if request.category:
            category = request.category
            category_confidence = 1.0
        elif analysis_result:
            category = IssueCategory(
                analysis_result.get("category", "general")
            )
            category_confidence = analysis_result.get(
                "category_confidence", 0.5
            )
        else:
            category = self._detect_category_from_text(
                request.issue_description
            )
            category_confidence = 0.6

        # Step 4: Resolve department
        dept_info = await self.dept_resolver.resolve_department(
            category=category.value,
            state=request.issue_state or "",
            city=request.issue_city or "",
            district=request.issue_district or "",
            latitude=request.issue_latitude,
            longitude=request.issue_longitude,
        )

        # Step 5: Generate RTI text
        user_name = self._get_user_name(user)
        user_address = self._get_user_address(user)

        rti_text = await self._generate_rti_text(
            user_name=user_name,
            user_address=user_address,
            user_phone=user.phone or "",
            user_email=user.email,
            issue_description=request.issue_description,
            issue_location=request.issue_location,
            category=category,
            department_name=dept_info.get("department_name", ""),
            pio_name=dept_info.get("pio_name", ""),
            pio_address=dept_info.get("pio_address", ""),
            analysis_result=analysis_result,
            custom_questions=request.custom_questions,
            language=request.language,
            is_bpl=user.is_bpl,
        )

        # Step 6: Create database record
        application = RTIApplication(
            user_id=user.id,
            tracking_number=tracking_number,
            category=category,
            issue_description=request.issue_description,
            issue_location=request.issue_location,
            issue_latitude=request.issue_latitude,
            issue_longitude=request.issue_longitude,
            issue_city=request.issue_city,
            issue_state=request.issue_state,
            issue_district=request.issue_district,
            issue_pincode=request.issue_pincode,
            issue_ward_number=request.issue_ward_number,
            department_type=DepartmentType(
                dept_info.get("department_type", "general")
            ),
            department_name=dept_info.get("department_name"),
            pio_name=dept_info.get("pio_name"),
            pio_address=dept_info.get("pio_address"),
            generated_subject=rti_text["subject"],
            generated_body=rti_text["body"],
            generated_questions=rti_text["questions"],
            status=ApplicationStatus.GENERATED,
            ai_category_confidence=category_confidence,
            ai_department_confidence=dept_info.get("confidence"),
            image_authenticity_score=(
                fraud_result["overall_score"] if fraud_result else None
            ),
            language=request.language,
            is_bpl_application=user.is_bpl,
            user_notes=request.user_notes,
        )

        self.db.add(application)
        await self.db.flush()

        logger.info(
            "rti_application_created",
            tracking_number=tracking_number,
            category=category.value,
            user_id=user.id,
        )

        return RTIGenerateResponse(
            tracking_number=tracking_number,
            status=ApplicationStatus.GENERATED,
            category=category,
            department_type=DepartmentType(
                dept_info.get("department_type", "general")
            ),
            department_name=dept_info.get("department_name"),
            pio_name=dept_info.get("pio_name"),
            pio_address=dept_info.get("pio_address"),
            generated_subject=rti_text["subject"],
            generated_body=rti_text["body"],
            generated_questions=rti_text["questions"],
            generated_pdf_url=None,
            ai_category_confidence=category_confidence,
            ai_department_confidence=dept_info.get("confidence"),
            image_authenticity_score=(
                fraud_result["overall_score"] if fraud_result else None
            ),
            estimated_fee=0.0 if user.is_bpl else RTIConstants.RTI_FEE_INR,
            portal_url=dept_info.get("portal_url"),
            created_at=application.created_at,
        )

    async def _generate_rti_text(
        self,
        user_name: str,
        user_address: str,
        user_phone: str,
        user_email: str,
        issue_description: str,
        issue_location: str,
        category: IssueCategory,
        department_name: str,
        pio_name: str,
        pio_address: str,
        analysis_result: Optional[Dict] = None,
        custom_questions: Optional[List[str]] = None,
        language: str = "en",
        is_bpl: bool = False,
    ) -> Dict[str, Any]:
        """Generate the complete RTI application text."""

        # Get questions from AI analysis or templates
        questions = []
        if analysis_result and analysis_result.get("recommended_questions"):
            questions = analysis_result["recommended_questions"]
        else:
            questions = self._get_template_questions(category, issue_location)

        # Add custom questions
        if custom_questions:
            questions.extend(custom_questions)

        # Remove duplicates while preserving order
        seen = set()
        unique_questions = []
        for q in questions:
            q_normalized = q.strip().lower()
            if q_normalized not in seen:
                seen.add(q_normalized)
                unique_questions.append(q.strip())
        questions = unique_questions

        # Generate subject
        subject = (
            f"Application under Section 6(1) of the Right to "
            f"Information Act, 2005 - Regarding "
            f"{category.value.replace('_', ' ').title()} at "
            f"{issue_location}"
        )

        # Format questions
        questions_text = ""
        for i, q in enumerate(questions, 1):
            questions_text += f"   ({self._roman(i)}) {q}\n\n"

        # Fee text
        if is_bpl:
            fee_text = (
                "I belong to the Below Poverty Line (BPL) category and "
                "am therefore exempt from the application fee as per "
                "Section 7(5) of the RTI Act, 2005. A copy of my "
                "BPL certificate is enclosed."
            )
        else:
            fee_text = (
                "I have enclosed the prescribed fee of Rs. 10/- "
                "(Rupees Ten Only) via Indian Postal Order / "
                "Online Payment as the application fee."
            )

        # Image description context
        image_context = ""
        if analysis_result and analysis_result.get("image_description"):
            image_context = (
                f"\n   Note: A photograph of the issue is enclosed "
                f"herewith showing: {analysis_result['image_description']}\n"
            )

        today = datetime.now().strftime("%d/%m/%Y")

        body = f"""To,
The {pio_name},
{department_name},
{pio_address}

Subject: {subject}

Respected Sir/Madam,

I, {user_name}, a citizen of India, hereby submit this application under Section 6(1) of the Right to Information Act, 2005, to seek the following information:

BACKGROUND:
The {category.value.replace('_', ' ')} at {issue_location} has been in a severely unsatisfactory condition. {issue_description}
{image_context}
PARTICULARS OF INFORMATION SOUGHT:

Kindly provide the following information pertaining to the above-mentioned issue:

{questions_text}
PERIOD OF INFORMATION: April 2023 to present date.

PREFERRED FORMAT: Certified copies of the relevant documents, file notings, orders, and reports.

FEE DETAILS:
{fee_text}

APPLICANT DETAILS:
Name: {user_name}
Address: {user_address}
Phone: {user_phone}
Email: {user_email}
Citizenship: Indian

I hereby declare that I am a citizen of India and the information sought does not fall within the restrictions set out under Section 8 of the RTI Act, 2005.

I request you to kindly provide the above information within 30 days as stipulated under Section 7(1) of the RTI Act, 2005.

Date: {today}
Place: {issue_location.split(',')[0].strip() if ',' in issue_location else issue_location}

Yours faithfully,
{user_name}"""

        return {
            "subject": subject,
            "body": body,
            "questions": questions,
        }

    def _get_template_questions(
        self, category: IssueCategory, location: str
    ) -> List[str]:
        """Get template questions based on category."""
        templates = {
            IssueCategory.ROAD_REPAIR: [
                f"Whether any budget was allocated for the repair/reconstruction of the road at {location} during the financial years 2023-24 and 2024-25? If yes, provide the sanctioned amount and a certified copy of the budget allocation order.",
                "If a budget was allocated, what is the current status of expenditure? Provide a certified copy of the expenditure statement.",
                "Whether any tender/contract was floated for the repair of this road? If yes, provide: (a) Name of the contractor/agency, (b) Date of award, (c) Total contract value, (d) Deadline for completion, (e) Certified copy of the work order.",
                "If the work has not started or is delayed, what are the recorded reasons for the delay? Provide a certified copy of the relevant file notings.",
                f"Name and designation of the officer(s) responsible for the maintenance and repair of the road at {location}.",
                "How many written complaints have been received regarding the condition of this road in the last 12 months? Provide dates and complaint reference numbers.",
                "What action has been taken on the above complaints? Provide a certified copy of the action-taken report.",
                "Whether any inspection of the road was conducted in the last 6 months? If yes, provide a certified copy of the inspection report.",
                "What is the expected timeline for completion of repair/reconstruction of this road?",
            ],
            IssueCategory.WATER_SUPPLY: [
                f"What is the scheduled water supply timing for the area at {location}?",
                "How many complaints regarding water supply disruption have been received from this area in the last 6 months?",
                "What action has been taken to address water supply issues in this area?",
                "Provide details of the water pipeline infrastructure maintenance budget for this area.",
                "Name and designation of the officer responsible for water supply in this area.",
                "Has any water quality test been conducted for this area in the last 3 months? If yes, provide the test results.",
                "What is the plan and timeline for resolving water supply issues in this area?",
            ],
            IssueCategory.ELECTRICITY: [
                f"How many power outage complaints have been registered from {location} in the last 6 months?",
                "What is the average power supply duration in this area per day?",
                "Has any infrastructure upgrade been planned for the electricity network in this area?",
                "Name and designation of the officer responsible for electricity supply.",
                "Provide details of transformer maintenance records for this area.",
                "What is the budget allocated for electrical infrastructure maintenance?",
                "What is the timeline for resolving the reported electricity issues?",
            ],
            IssueCategory.SANITATION: [
                f"What is the garbage collection schedule for {location}?",
                "How many sanitation workers are assigned to this area?",
                "How many complaints regarding sanitation have been received in the last 6 months?",
                "What budget has been allocated for sanitation and cleanliness in this area?",
                "Name and designation of the officer responsible for sanitation.",
                "Has any inspection been conducted regarding cleanliness in this area?",
                "What action plan exists for improving sanitation in this area?",
            ],
        }

        default_questions = [
            f"What budget has been allocated for addressing this issue at {location} in the current financial year?",
            "Provide the name and designation of the officer responsible for this matter.",
            "How many complaints have been received regarding this issue in the last 12 months?",
            "What action has been taken on previous complaints? Provide action-taken report.",
            "Has any inspection been conducted? If yes, provide the inspection report.",
            "What is the expected timeline for resolution of this issue?",
            "If any contractor has been appointed, provide complete contract details.",
        ]

        return templates.get(category, default_questions)

    def _generate_tracking_number(self) -> str:
        """Generate a unique tracking number."""
        now = datetime.now()
        prefix = "RTI"
        date_part = now.strftime("%Y%m%d")
        unique_part = uuid.uuid4().hex[:8].upper()
        return f"{prefix}-{date_part}-{unique_part}"

    def _get_user_name(self, user: User) -> str:
        """Decrypt and return user name."""
        if settings.ENCRYPTION_KEY:
            try:
                return security_manager.decrypt_pii(
                    user.full_name_encrypted
                )
            except Exception:
                return user.full_name_encrypted
        return user.full_name_encrypted

    def _get_user_address(self, user: User) -> str:
        """Build user address string."""
        parts = []
        if user.address_encrypted:
            if settings.ENCRYPTION_KEY:
                try:
                    parts.append(
                        security_manager.decrypt_pii(user.address_encrypted)
                    )
                except Exception:
                    parts.append(user.address_encrypted)
            else:
                parts.append(user.address_encrypted)
        if user.city:
            parts.append(user.city)
        if user.district:
            parts.append(f"District: {user.district}")
        if user.state:
            parts.append(user.state)
        if user.pincode:
            parts.append(f"Pincode: {user.pincode}")

        return ", ".join(parts) if parts else "Address not provided"

    def _detect_category_from_text(
        self, description: str
    ) -> IssueCategory:
        """Simple keyword-based category detection."""
        from config.constants import DEPARTMENT_KEYWORDS

        desc_lower = description.lower()
        for category, keywords in DEPARTMENT_KEYWORDS.items():
            if any(kw in desc_lower for kw in keywords):
                try:
                    return IssueCategory(category)
                except ValueError:
                    pass
        return IssueCategory.GENERAL

    @staticmethod
    def _roman(num: int) -> str:
        """Convert number to roman numeral."""
        val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
        syms = [
            'M', 'CM', 'D', 'CD', 'C', 'XC', 'L', 'XL',
            'X', 'IX', 'V', 'IV', 'I'
        ]
        roman_num = ''
        i = 0
        while num > 0:
            for _ in range(num // val[i]):
                roman_num += syms[i]
                num -= val[i]
            i += 1
        return roman_num.lower()