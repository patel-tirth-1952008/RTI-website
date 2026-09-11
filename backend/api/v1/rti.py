from fastapi import (
    APIRouter, Depends, HTTPException, status,
    Request, UploadFile, File, Form
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from config.database import get_db
from config.settings import settings
from schemas.rti import RTICreateRequest, RTIGenerateResponse
from services.rti_generator_service import RTIGeneratorService
from api.middleware.auth_middleware import get_current_user
from api.middleware.rate_limiter import limiter
from models.user import User
from models.rti_application import RTIApplication
from typing import Optional
import structlog
import io

logger = structlog.get_logger()
router = APIRouter(prefix="/rti", tags=["RTI Applications"])


@router.post(
    "/generate",
    response_model=RTIGenerateResponse,
    status_code=status.HTTP_201_CREATED
)
@limiter.limit("10/minute")
async def generate_rti(
    request: Request,
    issue_description: str = Form(...),
    issue_location: str = Form(...),
    issue_city: Optional[str] = Form(None),
    issue_state: Optional[str] = Form(None),
    issue_district: Optional[str] = Form(None),
    issue_pincode: Optional[str] = Form(None),
    issue_ward_number: Optional[str] = Form(None),
    issue_latitude: Optional[float] = Form(None),
    issue_longitude: Optional[float] = Form(None),
    category: Optional[str] = Form(None),
    language: str = Form("en"),
    user_notes: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Generate an RTI application.
    Upload an image of the issue and describe it.
    The system will:
    1. Validate and sanitize the image (anti-malware)
    2. Analyze the image for authenticity
    3. Detect the type of issue via Gemini AI
    4. Identify the correct government department
    5. Generate a complete RTI application
    """
    try:
        image_bytes = None
        image_filename = None

        if image:
            # 1. Content-Type Header Check
            if image.content_type not in settings.ALLOWED_IMAGE_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported image type: {image.content_type}."
                )

            # 2. File Size Check (Max 10MB)
            image_bytes = await image.read()
            max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
            if len(image_bytes) > max_size:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Image file too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB}MB."
                )

            # 3. Magic Byte & Integrity Verification (Anti-Malware)
            try:
                from PIL import Image as PILImage
                img = PILImage.open(io.BytesIO(image_bytes))
                img.verify()

                # Re-open after verify (Pillow requirement)
                img = PILImage.open(io.BytesIO(image_bytes))
                if img.format not in ["JPEG", "PNG", "WEBP"]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Uploaded file is not a valid JPEG, PNG, or WEBP image."
                    )
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Corrupted or invalid image file. Executable or non-image files are strictly rejected."
                )

            image_filename = image.filename

        # Parse category
        from config.constants import IssueCategory
        parsed_category = None
        if category:
            try:
                parsed_category = IssueCategory(category)
            except ValueError:
                pass

        # Create request object
        rti_request = RTICreateRequest(
            issue_description=issue_description,
            issue_location=issue_location,
            issue_city=issue_city,
            issue_state=issue_state,
            issue_district=issue_district,
            issue_pincode=issue_pincode,
            issue_ward_number=issue_ward_number,
            issue_latitude=issue_latitude,
            issue_longitude=issue_longitude,
            category=parsed_category,
            language=language,
            user_notes=user_notes,
        )

        # Generate RTI
        generator = RTIGeneratorService(db)
        result = await generator.create_rti_application(
            user=user,
            request=rti_request,
            image_bytes=image_bytes,
            image_filename=image_filename,
        )

        logger.info(
            "rti_generated",
            tracking_number=result.tracking_number,
            user_id=user.id,
        )

        return result

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("rti_generation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate RTI application. Please try again."
        )


@router.delete("/{tracking_number}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rti_application(
    tracking_number: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a draft or failed test RTI application."""
    result = await db.execute(
        select(RTIApplication).where(
            RTIApplication.tracking_number == tracking_number,
            RTIApplication.user_id == user.id,
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )

    await db.delete(application)
    await db.flush()
    logger.info(
        "rti_application_deleted",
        tracking_number=tracking_number,
        user_id=user.id,
    )