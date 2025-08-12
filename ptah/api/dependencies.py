import os
from pathlib import Path
from typing import Annotated
from fastapi import Depends
from ptah.env import ENV
from ptah.models.PtahConfig import PtahConfig
from ptah.utils.K8sVaultTokenProcessing import K8sVaultTokenProcessing
from ptah.utils.utils import load_ptah_config


def get_config() -> PtahConfig:
    config_path = Path("/opt/ptah_config.yaml")
    return load_ptah_config(config_path)


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
