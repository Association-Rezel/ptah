from fastapi import APIRouter

from .jwt import router as jwt_router
from ptah.env import ENV

if ENV.deploy_env == "dev":
    router = APIRouter(prefix="/dev", tags=["Dev"])
    router.include_router(jwt_router)
