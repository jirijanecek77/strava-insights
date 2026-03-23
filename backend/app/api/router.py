from fastapi import APIRouter

from app.api.routes.activities import router as activities_router
from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.best_efforts import router as best_efforts_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.health import router as health_router
from app.api.routes.me import router as me_router
from app.api.routes.sync import router as sync_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(me_router, tags=["users"])
api_router.include_router(admin_router, tags=["admin"])
api_router.include_router(sync_router, tags=["sync"])
api_router.include_router(dashboard_router, tags=["dashboard"])
api_router.include_router(activities_router, tags=["activities"])
api_router.include_router(best_efforts_router, tags=["best-efforts"])
