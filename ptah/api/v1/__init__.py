from fastapi import APIRouter

from .build import router as build_router
from .ptah_profiles import router as ptah_profiles_router
from .dev import router as dev_router

router = APIRouter(prefix="/v1")

router.include_router(build_router)
router.include_router(ptah_profiles_router)
router.include_router(dev_router)
