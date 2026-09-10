# Update backend/api/v1/__init__.py

from fastapi import APIRouter
from .auth import router as auth_router
from .rti import router as rti_router
from .media import router as media_router
from .tracking import router as tracking_router
from .admin import router as admin_router
from .filing import router as filing_router  # NEW

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(rti_router)
api_v1_router.include_router(media_router)
api_v1_router.include_router(tracking_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(filing_router)  # NEW