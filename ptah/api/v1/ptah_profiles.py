from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ptah.models import PtahConfig
from ptah.api.dependencies import get_config

router = APIRouter(prefix="/ptah_profiles", tags=["Ptah Profiles"])


@router.get("/")
def build_endpoint(
    config: Annotated[PtahConfig, Depends(get_config)],
):
    return JSONResponse(
        content=config.ptah_profiles,
        status_code=200,
    )


@router.get("/names")
def list_profiles(
    config: Annotated[PtahConfig, Depends(get_config)],
):
    """
    List all available Ptah profiles.
    """
    return JSONResponse(
        content=[profile.name for profile in config.ptah_profiles],
        status_code=200,
    )
