# backend/tests/test_rti.py

import pytest
from services.fraud_detection_service import FraudDetectionService
from services.rti_generator_service import RTIGeneratorService
from config.constants import IssueCategory


class TestFraudDetection:
    """Test fraud detection service."""

    def test_initialization(self):
        service = FraudDetectionService()
        assert service.ela_quality == 95
        assert len(service.suspicious_software) > 0

    def test_recommendation_text(self):
        service = FraudDetectionService()
        from config.constants import FraudCheckResult
        rec = service._get_recommendation(
            FraudCheckResult.AUTHENTIC, 0.9
        )
        assert "authentic" in rec.lower() or "proceeding" in rec.lower()


class TestCategoryDetection:
    """Test category detection from text."""

    def test_road_detection(self):
        from config.constants import DEPARTMENT_KEYWORDS
        desc = "The road near my house is broken"
        desc_lower = desc.lower()
        keywords = DEPARTMENT_KEYWORDS.get("road_repair", [])
        assert any(kw in desc_lower for kw in keywords)

    def test_water_detection(self):
        from config.constants import DEPARTMENT_KEYWORDS
        desc = "No water supply since 3 days"
        desc_lower = desc.lower()
        keywords = DEPARTMENT_KEYWORDS.get("water_supply", [])
        assert any(kw in desc_lower for kw in keywords)