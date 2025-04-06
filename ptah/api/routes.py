from fastapi import APIRouter
from ptah.api.build import router as build_router
from ptah.api.jwt import router as jwt_router

router = APIRouter()

router.include_router(build_router)
router.include_router(jwt_router)


@router.get("/")
def get_root():
    return "Welcome to the Ptah API!"
