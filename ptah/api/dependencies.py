import logging
import os
from pathlib import Path
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from netaddr import EUI, AddrFormatError, mac_unix_expanded
from ptah.env import ENV
from ptah.models.PtahConfig import PtahConfig
from ptah.utils.K8sVaultTokenProcessing import K8sVaultTokenProcessing
from ptah.utils.utils import load_ptah_config
from rezel_vault_jwt.jwt_transit_manager import JwtTransitManager
from common_models.base import validate_mac


def get_config() -> PtahConfig:
    return load_ptah_config(ENV.config_path)


def read_secrets(config: Annotated[PtahConfig, Depends(get_config)]) -> dict:
    secrets = {}
    for credential in config.credentials.keys():
        if credential == "K8S_VAULT_TOKEN":
            secrets[credential] = K8sVaultTokenProcessing(
                ENV.vault_url, ENV.vault_role_name
            ).get_vault_token()
            continue
        if credential not in os.environ:
            raise RuntimeError(
                f"Environment variable '{credential}' not found. "
                "Please set it in your environment."
            )
        secrets[credential] = os.getenv(credential)

    if secrets == {}:
        raise RuntimeError("No secrets found in environment variables.")
    return secrets


def verify_jwt(token: str):
    k8s_token_processing = K8sVaultTokenProcessing(
        vault_url=ENV.vault_url,
        vault_role_name=ENV.vault_role_name,
    )
    jwt_manager = JwtTransitManager(
        vault_token=k8s_token_processing.get_vault_token(),
        vault_base_url=ENV.vault_url,
        transit_mount=ENV.vault_transit_mount,
        transit_key=ENV.vault_transit_key,
    )
    is_valid = jwt_manager.verify_jwt(token)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Decode the JWT token to extract payload
    payload = JwtTransitManager.decode_jwt(token)
    return payload


# Define a dependency using HTTPBearer
bearer_scheme = HTTPBearer()


def jwt_required(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
):
    logging.debug("JWT required dependency called.")
    return verify_jwt(credentials.credentials)


def get_credentials(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
):
    return credentials.credentials


def check_mac_matches_payload(
    mac: str, payload: Annotated[dict, Depends(jwt_required)]
) -> dict:
    mac = validate_mac(mac)
    token_mac: str = payload.get("mac")
    if not token_mac:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MAC address not present in token payload",
        )

    if str(mac) != token_mac:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MAC address in token does not match requested MAC",
        )

    return payload
