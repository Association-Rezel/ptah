import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import Depends
from ptah.models.PtahConfig import PtahConfig
from ptah.utils.utils import load_ptah_config


def get_config() -> PtahConfig:
    config_path = Path("/opt/ptah_config.yaml")
    return load_ptah_config(config_path)


def read_secrets(config: PtahConfig = Depends(get_config)) -> dict:
    secrets = {}

    for credential in config.credentials.keys():
        secrets[credential] = os.getenv(credential)
        if secrets[credential] is None:
            raise RuntimeError(
                f"Environment variable '{credential}' not found. "
                "Please set it in your environment."
            )
    if secrets == {}:
        raise RuntimeError("No secrets found in environment variables.")
    return secrets
