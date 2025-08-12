"""JWT API for encoding and decoding JWTs using Vault Transit. This is intended for dev."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from rezel_vault_jwt.jwt_transit_manager import JwtTransitManager
from rezel_vault_jwt.jwt_payload_builder import JwtPayloadBuilder

from ptah.env import ENV
from ptah.models.build import BuildPrepareRequest
from ptah.models import PtahConfig, PtahProfile, PortableMac
from ptah.api.dependencies import get_config, read_secrets

router = APIRouter(
    prefix="/jwt",
)


class JwtPayload(BaseModel):
    """Request model for endpoints that receive a JWT in the body."""

    jwt: str


bearer_scheme = HTTPBearer()


def check_profile_exists(profile_name: str, config: PtahConfig) -> PtahProfile | None:
    """Finds and returns a PtahProfile by name if it exists."""
    for ptah_profile in config.ptah_profiles:
        if ptah_profile.name == profile_name:
            return ptah_profile
    return None


def get_jwt_manager(
    profile_name: str,
    config: PtahConfig,
    secrets: dict,
) -> JwtTransitManager:
    """
    Initializes and returns a JwtTransitManager for a given profile.
    Raises HTTPException if the profile or its configuration is invalid.
    """
    if (ptah_profile := check_profile_exists(profile_name, config)) is None:
        raise HTTPException(
            status_code=404,
            detail=f"Profile '{profile_name}' not found.",
        )

    jwt_transit_file = None
    if ptah_profile.files and ptah_profile.files.router_specific_files:
        for specific_file in ptah_profile.files.router_specific_files:
            if specific_file.type == "jwt_from_vault_transit":
                jwt_transit_file = specific_file
                break

    if not jwt_transit_file:
        raise HTTPException(
            status_code=400,
            detail=f"No 'jwt_from_vault_transit' configuration found in profile '{profile_name}'.",
        )
    if not jwt_transit_file.jwt_from_vault_transit:
        raise HTTPException(
            status_code=400,
            detail=f"JWT transit information is incomplete in profile '{profile_name}'.",
        )

    return JwtTransitManager(
        vault_token=secrets[
            jwt_transit_file.jwt_from_vault_transit.credentials.vault_token
        ],
        vault_base_url=ENV.vault_url,
        transit_mount=jwt_transit_file.jwt_from_vault_transit.transit_mount,
        transit_key=jwt_transit_file.jwt_from_vault_transit.transit_key,
    )


@router.post("/encode/{mac}", summary="Issue a new JWT")
def jwt_encode(
    mac: PortableMac,
    request_data: BuildPrepareRequest,
    config: Annotated[PtahConfig, Depends(get_config)],
    secrets: Annotated[dict, Depends(read_secrets)],
):
    """
    Encodes and signs a new JWT for a given MAC address and profile.
    The profile specified in the request body must contain a 'jwt_from_vault_transit' config.
    """
    try:
        jwt_manager = get_jwt_manager(request_data.profile, config, secrets)
    except HTTPException as e:
        raise e

    jwt_payload_builder = JwtPayloadBuilder()
    payload = jwt_payload_builder.create_ptah_payload(mac=mac)

    try:
        encoded_jwt = jwt_manager.issue_jwt(payload)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to issue JWT: {e}",
        )

    return JSONResponse(
        content={
            "message": "JWT issued successfully.",
            "jwt": encoded_jwt,
            "mac": mac,
        },
        status_code=200,
    )


@router.post("/decode", summary="Decode a JWT payload (no signature verification)")
def jwt_decode(
    payload: JwtPayload,
):
    """
    Decodes a JWT from the request body and returns its payload.
    This endpoint does NOT verify the signature and is completely stateless.
    """
    try:
        decoded_payload = JwtTransitManager.decode_jwt(payload.jwt)
        return JSONResponse(content=decoded_payload, status_code=200)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to decode JWT: {e}",
        )


@router.post("/verify", summary="Verify a JWT signature from Authorization header")
def jwt_verify(
    token: Annotated[HTTPAuthorizationCredentials, Security(bearer_scheme)],
    profile: Annotated[
        str, Query(description="The profile name used to issue the JWT.")
    ],
    config: Annotated[PtahConfig, Depends(get_config)],
    secrets: Annotated[dict, Depends(read_secrets)],
):
    """
    Verifies a JWT's signature using the Vault transit engine.
    The JWT must be passed in the 'Authorization: Bearer <token>' header.
    """
    try:
        jwt_manager = get_jwt_manager(profile, config, secrets)
        is_valid = jwt_manager.verify_jwt(token.credentials)

        if is_valid:
            return JSONResponse(
                content={"status": "valid", "message": "JWT signature is valid."},
                status_code=200,
            )
        else:
            raise HTTPException(
                status_code=401,
                detail="JWT signature is invalid.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to verify JWT: {e}",
        )
