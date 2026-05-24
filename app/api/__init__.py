from fastapi import APIRouter

from app.core.config import settings
from app.api.admin import router as admin_router
from app.api.archive_entries import router as archive_entries_router
from app.api.auth import router as auth_router
from app.api.collections import router as collections_router
from app.api.developers import router as developers_router
from app.api.franchises import router as franchises_router
from app.api.jobs import router as jobs_router
from app.api.permissions import router as permissions_router
from app.api.publishers import router as publishers_router
from app.api.roles import router as roles_router
from app.api.search import router as search_router
from app.api.tags import router as tags_router
from app.api.users import router as users_router

api_router = APIRouter(prefix=settings.API_PREFIX)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(permissions_router)
api_router.include_router(archive_entries_router)
api_router.include_router(collections_router)
api_router.include_router(tags_router)
api_router.include_router(developers_router)
api_router.include_router(publishers_router)
api_router.include_router(franchises_router)
api_router.include_router(search_router)
api_router.include_router(jobs_router)
api_router.include_router(admin_router)
