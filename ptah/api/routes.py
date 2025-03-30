from fastapi import APIRouter
from .build import router as build_router

router = APIRouter()

router.include_router(build_router)

@router.get("/hello")
def hello(name: str = "World"):
    return "Hello, {name}!"
