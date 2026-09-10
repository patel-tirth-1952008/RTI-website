# backend/api/v1/admin.py

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from config.database import get_db
from api.middleware.auth_middleware import require_admin
from api.middleware.rate_limiter import limiter
from models.user import User
from models.rti_application import RTIApplication
from config.constants import ApplicationStatus
from typing import Dict, Any

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats", response_model=Dict[str, Any])
@limiter.limit("30/minute")
async def get_system_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Get system-wide statistics (admin only)."""
    # Total users
    user_count = await db.execute(select(func.count(User.id)))
    total_users = user_count.scalar()

    # Total applications
    app_count = await db.execute(
        select(func.count(RTIApplication.id))
    )
    total_applications = app_count.scalar()

    # Applications by status
    status_counts = {}
    for app_status in ApplicationStatus:
        count = await db.execute(
            select(func.count(RTIApplication.id)).where(
                RTIApplication.status == app_status
            )
        )
        status_counts[app_status.value] = count.scalar()

    return {
        "total_users": total_users,
        "total_applications": total_applications,
        "applications_by_status": status_counts,
    }