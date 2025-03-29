import os
import git
from pathlib import Path
from shutil import rmtree
from models.PtahConfig import *
import requests
import zstandard as zstd
import io
import tarfile

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
        print("No credentials provided.")
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
