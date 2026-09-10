# backend/schemas/media.py

from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from config.constants import MediaType, FraudCheckResult


class MediaUploadResponse(BaseModel):
    id: str
    original_filename: str
    file_url: str
    thumbnail_url: Optional[str]
    media_type: MediaType
    file_size_bytes: int
    fraud_check_result: Optional[FraudCheckResult]
    fraud_check_score: Optional[float]
    ai_description: Optional[str]
    ai_detected_issues: Optional[List[str]]
    exif_data: Optional[Dict[str, Any]]
    gps_latitude: Optional[float]
    gps_longitude: Optional[float]
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class FraudCheckResponse(BaseModel):
    overall_result: FraudCheckResult
    overall_score: float
    checks: List[Dict[str, Any]]
    recommendation: str