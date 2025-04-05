from fastapi import APIRouter
from ptah.api.build import router as build_router

router = APIRouter()

router.include_router(build_router)


@router.get("/")
def get_root():
    return "Welcome to the Ptah API!"
