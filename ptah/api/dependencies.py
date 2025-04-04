import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import Request, Depends
import yaml
from models.PtahConfig import PtahConfig
from utils.utils import load_ptah_config


def get_config() -> PtahConfig:
    config_path = Path("/opt/ptah_config.yaml")
    return load_ptah_config(config_path)


def read_secrets(config: PtahConfig = Depends(get_config)) -> dict:
    secrets = {}
    ptah_secrets_source = os.getenv("PTAH_SECRETS_SOURCE")
    if os.getenv("PTAH_SECRETS_SOURCE") == "k8s":
        load_dotenv("/vault/secrets/.env")
    elif ptah_secrets_source == "environ":
        pass
    for credential in config.credentials.keys():
        secrets[credential] = os.getenv(credential)
    if secrets == {}:
        raise RuntimeError("No secrets found in environment variables.")
    return secrets
