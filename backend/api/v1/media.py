# backend/api/v1/media.py

from fastapi import (
    APIRouter, Depends, HTTPException, status,
    Request, UploadFile, File
)
from sqlalchemy.ext.asyncio import AsyncSession
from config.database import get_db
from config.settings import settings
from schemas.media import MediaUploadResponse, FraudCheckResponse
from services.fraud_detection_service import FraudDetectionService
from api.middleware.auth_middleware import get_current_user
from api.middleware.rate_limiter import limiter
from models.user import User
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/media", tags=["Media"])


@router.post("/analyze", response_model=FraudCheckResponse)
@limiter.limit("10/minute")
async def analyze_image(
    request: Request,
    image: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """
    Analyze an image for authenticity.
    Checks for AI generation, manipulation, and metadata consistency.
    """
    if image.content_type not in settings.ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image type: {image.content_type}"
        )

    image_bytes = await image.read()
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(image_bytes) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image too large. Maximum: {settings.MAX_UPLOAD_SIZE_MB}MB"
        )

    fraud_detector = FraudDetectionService()
    result = await fraud_detector.analyze_image(
        image_bytes, image.filename or "image.jpg"
    )

    return FraudCheckResponse(
        overall_result=result["overall_result"],
        overall_score=result["overall_score"],
        checks=result["checks"],
        recommendation=result["recommendation"],
    )