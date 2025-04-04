from fastapi import APIRouter
from .build import router as build_router

router = APIRouter()

router.include_router(build_router)


@router.get("/")
def getRoot():
    return "Welcome to the Ptah API!"
