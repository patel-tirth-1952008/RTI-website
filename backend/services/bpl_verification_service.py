"""
BPL VERIFICATION SERVICE
Verifies BPL status from uploaded card images using OCR.
"""

import re
import io
from typing import Dict, Optional, Any
from PIL import Image
from enum import Enum
import structlog

logger = structlog.get_logger()


class BPLCardType(str, Enum):
    BPL_CARD = "bpl_card"
    ANTYODAYA = "antyodaya_ann_yojana"
    PRIORITY_HOUSEHOLD = "priority_household"
    RATION_CARD = "ration_card"
    UNKNOWN = "unknown"


class BPLVerificationResult:
    def __init__(self, is_verified, card_type, confidence, extracted_details, message, document_path=None):
        self.is_verified = is_verified
        self.card_type = card_type
        self.confidence = confidence
        self.extracted_details = extracted_details
        self.message = message
        self.document_path = document_path


class BPLVerificationService:
    """Verifies BPL status from uploaded documents."""

    CARD_PATTERNS = {
        "gujarat": r"GJ\d{2}[A-Z]{2}\d{6,8}",
        "maharashtra": r"MH\d{2}[A-Z]{2}\d{6,8}",
        "karnataka": r"KA\d{2}[A-Z]{2}\d{6,8}",
        "delhi": r"DL\d{2}[A-Z]{2}\d{6,8}",
        "rajasthan": r"RJ\d{2}[A-Z]{2}\d{6,8}",
        "tamil_nadu": r"TN\d{2}[A-Z]{2}\d{6,8}",
        "uttar_pradesh": r"UP\d{2}[A-Z]{2}\d{6,8}",
        "generic": r"[A-Z]{2}\d{2}[A-Z]{0,2}\d{5,10}",
    }

    BPL_KEYWORDS = [
        "bpl", "below poverty", "antyodaya", "aay",
        "priority household", "phh", "nfsa",
        "antodaya", "anna yojana",
    ]

    async def verify_bpl_document(self, image_bytes: bytes, state: str = "", declared_bpl: bool = True) -> BPLVerificationResult:
        if not declared_bpl:
            return BPLVerificationResult(
                is_verified=False, card_type=BPLCardType.UNKNOWN,
                confidence=1.0, extracted_details={},
                message="User has not declared BPL status.",
            )

        try:
            extracted_text = await self._ocr_image(image_bytes)

            if not extracted_text or len(extracted_text.strip()) < 10:
                return BPLVerificationResult(
                    is_verified=False, card_type=BPLCardType.UNKNOWN,
                    confidence=0.3, extracted_details={"raw_text": extracted_text or ""},
                    message="Could not read the document. Please upload a clearer photo.",
                )

            text_lower = extracted_text.lower()
            found_keywords = [kw for kw in self.BPL_KEYWORDS if kw in text_lower]
            card_number = self._extract_card_number(extracted_text, state)

            card_type = BPLCardType.UNKNOWN
            if "antyodaya" in text_lower or "aay" in text_lower:
                card_type = BPLCardType.ANTYODAYA
            elif "priority" in text_lower or "phh" in text_lower:
                card_type = BPLCardType.PRIORITY_HOUSEHOLD
            elif "bpl" in text_lower:
                card_type = BPLCardType.BPL_CARD
            elif "ration" in text_lower or "card" in text_lower:
                card_type = BPLCardType.RATION_CARD

            confidence = 0.3
            if found_keywords:
                confidence += 0.3
            if card_number:
                confidence += 0.2
            if card_type in [BPLCardType.ANTYODAYA, BPLCardType.BPL_CARD]:
                confidence += 0.2
            confidence = min(1.0, confidence)

            is_verified = confidence >= 0.6 and len(found_keywords) > 0

            if is_verified:
                message = "BPL document verified. RTI fee waived."
            elif confidence >= 0.4:
                message = "Document appears to be a BPL card. Fee subject to PIO confirmation."
            else:
                message = "Could not verify BPL status. Standard fee of Rs. 10 applies."

            return BPLVerificationResult(
                is_verified=is_verified, card_type=card_type,
                confidence=confidence,
                extracted_details={
                    "raw_text": extracted_text[:500],
                    "found_keywords": found_keywords,
                    "card_number": card_number,
                    "card_type": card_type.value,
                },
                message=message,
            )

        except Exception as e:
            logger.error("bpl_verification_failed", error=str(e))
            return BPLVerificationResult(
                is_verified=False, card_type=BPLCardType.UNKNOWN,
                confidence=0.0, extracted_details={},
                message="BPL verification failed: " + str(e),
            )

    async def _ocr_image(self, image_bytes: bytes) -> str:
        """Extract text from image using Tesseract or EasyOCR."""
        try:
            import pytesseract
            image = Image.open(io.BytesIO(image_bytes))
            image = image.convert("L")
            image = image.point(lambda x: 0 if x < 128 else 255)
            text = pytesseract.image_to_string(image, config="--psm 6")
            if text and len(text.strip()) > 10:
                return text.strip()
        except ImportError:
            logger.warning("pytesseract_not_installed")
        except Exception as e:
            logger.warning("tesseract_ocr_failed", error=str(e))

        try:
            import easyocr
            reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            image_array = Image.open(io.BytesIO(image_bytes))
            import numpy as np
            results = reader.readtext(np.array(image_array))
            if results:
                return " ".join([r[1] for r in results])
        except ImportError:
            logger.warning("easyocr_not_installed")
        except Exception as e:
            logger.warning("easyocr_failed", error=str(e))

        return ""

    def _extract_card_number(self, text: str, state: str) -> Optional[str]:
        """Extract ration/BPL card number from OCR text."""
        state_key = state.lower().replace(" ", "_").strip()
        pattern = self.CARD_PATTERNS.get(state_key, self.CARD_PATTERNS["generic"])

        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)

        match = re.search(self.CARD_PATTERNS["generic"], text, re.IGNORECASE)
        if match:
            return match.group(0)

        return None