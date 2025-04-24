from fastapi import APIRouter
from ptah.api.build import router as build_router
from ptah.api.jwt import router as jwt_router
from ptah.env import ENV

router = APIRouter()

router.include_router(build_router)

# This is a dangerous endpoint (arbitrary jwt)
# It should only be used in dev mode: maybe another way ?
if ENV.deploy_env == "dev":
    router.include_router(jwt_router)


@router.get("/")
def get_root():
    return "Welcome to the Ptah API!"
