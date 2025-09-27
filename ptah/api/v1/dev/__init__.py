from fastapi import APIRouter

from .jwt import router as jwt_router
from ptah.env import ENV

router = APIRouter(prefix="/dev", tags=["Dev"])

if ENV.deploy_env == "dev" or ENV.deploy_env == "local":
    router.include_router(jwt_router)
