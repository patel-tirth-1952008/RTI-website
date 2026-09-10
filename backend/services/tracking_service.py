# backend/services/tracking_service.py

from datetime import datetime, timezone, timedelta
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models.rti_application import RTIApplication
from schemas.rti import RTIStatusResponse, RTIListResponse
from config.constants import ApplicationStatus, RTIConstants
import structlog

logger = structlog.get_logger()


class TrackingService:
    """Service for tracking RTI application status."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_status(
        self,
        tracking_number: str,
        user_id: str
    ) -> Optional[RTIStatusResponse]:
        """Get status of a specific RTI application."""
        result = await self.db.execute(
            select(RTIApplication).where(
                RTIApplication.tracking_number == tracking_number,
                RTIApplication.user_id == user_id,
            )
        )
        application = result.scalar_one_or_none()
        if not application:
            return None

        return self._to_status_response(application)

    async def get_user_applications(
        self,
        user_id: str,
        page: int = 1,
        per_page: int = 10,
        status: Optional[ApplicationStatus] = None,
    ) -> RTIListResponse:
        """Get paginated list of user's RTI applications."""
        query = select(RTIApplication).where(
            RTIApplication.user_id == user_id
        )

        if status:
            query = query.where(RTIApplication.status == status)

        # Count total
        count_query = select(func.count()).select_from(
            query.subquery()
        )
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Paginate
        query = query.order_by(
            RTIApplication.created_at.desc()
        ).offset(
            (page - 1) * per_page
        ).limit(per_page)

        result = await self.db.execute(query)
        applications = result.scalars().all()

        return RTIListResponse(
            total=total,
            page=page,
            per_page=per_page,
            applications=[
                self._to_status_response(app) for app in applications
            ],
        )

    async def update_status(
        self,
        tracking_number: str,
        new_status: ApplicationStatus,
        portal_reference: Optional[str] = None,
        response_summary: Optional[str] = None,
    ) -> Optional[RTIStatusResponse]:
        """Update application status."""
        result = await self.db.execute(
            select(RTIApplication).where(
                RTIApplication.tracking_number == tracking_number
            )
        )
        application = result.scalar_one_or_none()
        if not application:
            return None

        application.status = new_status
        application.updated_at = datetime.now(timezone.utc)

        if portal_reference:
            application.portal_reference_number = portal_reference

        if new_status == ApplicationStatus.FILED_SUCCESSFULLY:
            application.filing_date = datetime.now(timezone.utc)
            application.response_due_date = (
                datetime.now(timezone.utc)
                + timedelta(days=RTIConstants.RTI_RESPONSE_DAYS)
            )

        if response_summary:
            application.response_summary = response_summary
            application.response_received_date = datetime.now(timezone.utc)

        await self.db.flush()

        logger.info(
            "application_status_updated",
            tracking_number=tracking_number,
            new_status=new_status.value,
        )

        return self._to_status_response(application)

    def _to_status_response(
        self, app: RTIApplication
    ) -> RTIStatusResponse:
        """Convert application model to status response."""
        days_remaining = None
        if app.response_due_date:
            delta = app.response_due_date - datetime.now(timezone.utc)
            days_remaining = max(0, delta.days)

        return RTIStatusResponse(
            tracking_number=app.tracking_number,
            portal_reference_number=app.portal_reference_number,
            status=app.status,
            category=app.category,
            department_name=app.department_name,
            filing_date=app.filing_date,
            response_due_date=app.response_due_date,
            response_received_date=app.response_received_date,
            response_summary=app.response_summary,
            days_remaining=days_remaining,
            created_at=app.created_at,
            updated_at=app.updated_at,
        )