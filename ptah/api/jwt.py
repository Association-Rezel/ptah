"""JWT API for encoding and decoding JWTs using Vault Transit. This is intended for dev."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from ptah.env import ENV
from ptah.models.build import BuildPrepareRequest
from ptah.models import PtahConfig, PtahProfile
from ptah.models import PortableMac
from ptah.utils.JwtTransitManager import JwtTransitManager
from ptah.api.dependencies import get_config, read_secrets

router = APIRouter()


def check_profile_exists(profile: str, config: PtahConfig) -> PtahProfile:
    for ptah_profile in config.ptah_profiles:
        if ptah_profile.name == profile:
            return ptah_profile
    return None


@router.post("/jwt/encode/{mac}")
def jwt_encode(
    request: Request,
    mac: PortableMac,
    request_data: BuildPrepareRequest,
    config: Annotated[PtahConfig, Depends(get_config)],
    secrets: Annotated[dict, Depends(read_secrets)],
):
    mac_fc = mac.to_filename_compliant()
    if (ptah_profile := check_profile_exists(request_data.profile, config)) is None:
        return HTTPException(
            status_code=404,
            detail=f"Profile {request_data.profile} not found.",
        )

    jwt_transit_file = None
    for specific_file in ptah_profile.files.router_specific_files:
        if specific_file.type == "jwt_from_vault_transit":
            jwt_transit_file = specific_file
            break
    if not jwt_transit_file:
        return HTTPException(
            status_code=400,
            detail="No JWT transit file found in the profile.",
        )
    if not jwt_transit_file.jwt_from_vault_transit:
        return HTTPException(
            status_code=400,
            detail="JWT transit file information is missing.",
        )

    jwt_manager = JwtTransitManager(
        secrets[jwt_transit_file.jwt_from_vault_transit.credentials.vault_token],
        ENV.vault_url,
        jwt_transit_file.jwt_from_vault_transit.transit_mount,
        jwt_transit_file.jwt_from_vault_transit.transit_key,
    )

    payload = {
        "mac": mac,
        "mac_fc": mac_fc,
    }
    try:
        encoded = jwt_manager.issue_jwt(payload)
    except Exception as e:
        return HTTPException(
            status_code=500,
            detail=f"Failed to issue JWT: {e}",
        )

    return JSONResponse(
        content={
            "message": "JWT Issued successfully.",
            "jwt": encoded,
            "mac": mac,
        },
        status_code=200,
    )
