# backend/api/v1/tracking.py

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from config.database import get_db
from schemas.rti import RTIStatusResponse, RTIListResponse
from services.tracking_service import TrackingService
from api.middleware.auth_middleware import get_current_user
from api.middleware.rate_limiter import limiter
from models.user import User
from typing import Optional
from config.constants import ApplicationStatus

router = APIRouter(prefix="/tracking", tags=["Tracking"])


@router.get("/{tracking_number}", response_model=RTIStatusResponse)
@limiter.limit("30/minute")
async def get_application_status(
    request: Request,
    tracking_number: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get status of a specific RTI application."""
    tracking_service = TrackingService(db)
    result = await tracking_service.get_status(
        tracking_number, user.id
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )

    return result


@router.get("/", response_model=RTIListResponse)
@limiter.limit("30/minute")
async def list_applications(
    request: Request,
    page: int = 1,
    per_page: int = 10,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all RTI applications for the current user."""
    parsed_status = None
    if status_filter:
        try:
            parsed_status = ApplicationStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}"
            )

    tracking_service = TrackingService(db)
    return await tracking_service.get_user_applications(
        user_id=user.id,
        page=max(1, page),
        per_page=min(50, max(1, per_page)),
        status=parsed_status,
    )