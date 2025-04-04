import os
import git
from pathlib import Path
from shutil import rmtree

import yaml
from models.PtahConfig import *
import requests
import zstandard as zstd
import io
import tarfile


def load_ptah_config(config_path: Path) -> PtahConfig:
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file {config_path} does not exist")

    with open(config_path, "r") as file:
        config_data = yaml.safe_load(file)
    return PtahConfig.model_validate(config_data)


def mac_to_filename_compliant(mac: str) -> str:
    return mac.replace(":", "-").replace("_", "-").replace(".", "_")


def extract_tar_zst(input_path: Path, output_dir: Path):
    with open(input_path, "rb") as compressed_file:
        dctx = zstd.ZstdDecompressor()
        with dctx.stream_reader(compressed_file) as reader:
            with tarfile.open(fileobj=io.BytesIO(reader.read()), mode="r:") as tar:
                tar.extractall(path=output_dir, filter="tar")


def build_git_http_url(url: HttpUrl, username: str, password: str) -> str:
    protocol = url.scheme
    rest = url.host

    # Rebuild netloc (optionally includes port and path)
    if url.port:
        rest += f":{url.port}"
    if url.path:
        rest += url.path

    return HttpUrl(f"{protocol}://{username}:{password}@{rest}")


def recreate_dir(path: Path):
    if path.is_dir():
        rmtree(path)
    elif path.exists():
        raise RuntimeError(f"Error: '{path}' exists and is not a directory.")
    path.mkdir(parents=True, exist_ok=True)


def echo_to_file(file: Path, content: str):
    with open(file, "w") as f:
        f.write(content)


def get_secrets(credentials: Optional[Dict[str, Optional[Credential]]]) -> dict:
    if not credentials:
        raise ValueError("No credentials provided in the configuration.")
    secrets = {}
    for credential_name, credential in credentials.items():
        if credential.source == "environ":
            secrets[credential_name] = os.getenv(credential_name)
        else:
            raise ValueError(f"Unsupported credential source: {credential.source}")
    return secrets


def clone_git_repo(file: FileEntry, dest: Path, username: str, password: str):
    if file.git.type == "http":
        if not username or not password:
            raise ValueError("Missing Git credentials in environment.")
        url = build_git_http_url(file.git.url, username, password)
        git.Repo.clone_from(url, dest)
    elif file.git.type == "ssh":
        raise NotImplementedError("SSH not supported yet")
    else:
        raise ValueError("Unsupported Git type")
