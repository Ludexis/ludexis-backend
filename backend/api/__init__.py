from fastapi import APIRouter

from app.api.auth.router import router as auth_router
from app.api.archive_entries.router import router as archive_router
from app.api.collections.router import router as collections_router
from app.api.users.router import router as users_router
from app.api.roles.router import router as roles_router
from app.api.permissions.router import router as permissions_router
from app.api.tags.router import router as tags_router
from app.api.developers.router import router as developers_router
from app.api.publishers.router import router as publishers_router
from app.api.franchises.router import router as franchises_router
from app.api.genres.router import router as genres_router
from app.api.metadata.router import router as metadata_router
from app.api.jobs.router import router as jobs_router
from app.api.search.router import router as search_router
from app.api.admin.router import router as admin_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(archive_router)
api_router.include_router(collections_router)
api_router.include_router(tags_router)
api_router.include_router(developers_router)
api_router.include_router(publishers_router)
api_router.include_router(franchises_router)
api_router.include_router(genres_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(permissions_router)
api_router.include_router(metadata_router)
api_router.include_router(jobs_router)
api_router.include_router(search_router)
api_router.include_router(admin_router)
