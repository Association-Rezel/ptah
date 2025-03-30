from pathlib import Path
from fastapi import Request, Depends
import yaml
from models.PtahConfig import PtahConfig
from utils.utils import load_ptah_config

def get_config(request: Request) -> PtahConfig:
    config_path = Path("/opt/ptah_config.yaml")
    return load_ptah_config(config_path)