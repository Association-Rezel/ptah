from fastapi import APIRouter

from .build import router as build_router
from .dev import router as dev_router

router = APIRouter(prefix="/v1")

router.include_router(build_router)
router.include_router(dev_router)
