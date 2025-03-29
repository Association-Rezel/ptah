import argparse
import shutil
import sys
import os
import yaml
import git
from pathlib import Path
from shutil import rmtree
from dotenv import load_dotenv
from models import *
import requests
import zstandard as zstd
import io
import tarfile

# ------------------------------- Helper Functions ------------------------------ #
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

def clone_git_repo(file: FileEntry, dest: Path):
    if file.git.type == "http":
        username = SECRETS[file.git.credentials.username_credential]
        password = SECRETS[file.git.credentials.password_credential]
        if not username or not password:
            raise ValueError("Missing Git credentials in environment.")
        url = build_git_http_url(file.git.url, username, password)
        git.Repo.clone_from(url, dest)
    elif file.git.type == "ssh":
        raise NotImplementedError("SSH not supported yet")
    else:
        raise ValueError("Unsupported Git type")

def handle_git_for_profile(file: FileEntry):
    clone_git_repo(file, GIT_REPO_PATH / f"{file.name}")

def handle_files_for_profile(file: FileEntry):
    if file.type == "git":
        handle_git_for_profile(file)
    elif file.type == "local":
        raise NotImplementedError("Local file handling not implemented yet")
    else:
        raise ValueError(f"Invalid file type: {file.type}")

def fetch_openwrt_image_builder(
    profile: PtahProfile, profile_path: Path, tmp_path: Path
):
    openwrt_version = profile.openwrt_profile.openwrt_version
    target = profile.openwrt_profile.target
    arch = profile.openwrt_profile.arch
    target_url = f"{OPENWRT_BASE_RELEASES_URL}/{openwrt_version}/targets/{target}/{arch}"
    archive_name = f"openwrt-imagebuilder-{openwrt_version}-{target}-{arch}{OPENWRT_BUILDER_FILE_EXT}"
    image_builder_url = f"{target_url}/{archive_name}"

    response = requests.get(image_builder_url, stream=True)
    response.raise_for_status()

    archive_path = tmp_path / archive_name
    with open(archive_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    unpack_dir = profile_path
    unpack_dir.mkdir(parents=True, exist_ok=True)
    extract_tar_zst(archive_path, unpack_dir)
    # The .stem.stem is used to remove .tar.zst from the archive name
    archive_extracted_path = Path(Path(archive_name).stem).stem
    echo_to_file(profile_path / "builder_folder", f"{archive_extracted_path}\n")
    

# ---------------------------------- Main Logic --------------------------------- #
def main(ptah_config: PtahConfig):
    for path in [GIT_REPO_PATH, BUILDERS_PATH, OUTPUT_PATH]:
        recreate_dir(path)

    for profile in ptah_config.ptah_profiles:
        profile_path = BUILDERS_PATH / profile.name
        tmp_path = profile_path / "tmp"
        for path in [profile_path, tmp_path]:
            recreate_dir(path)

        for file in profile.files.profile_shared_files:
            handle_files_for_profile(file)

        fetch_openwrt_image_builder(profile, profile_path, tmp_path)
        rmtree(tmp_path)

# --------------------------------- Entry Point --------------------------------- #
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ptah Configuration Processor")
    parser.add_argument("--config", required=True, help="Path to Ptah configuration file")
    parser.add_argument("--docker-secrets-mount", help="Docker source file for secrets")
    args = parser.parse_args()

    if not args.docker_secrets_mount:
        raise ValueError("Please provide the source of the secrets")

    load_dotenv(args.docker_secrets_mount)

    if not args.config:
        raise ValueError("Please provide path to configuration file")

    config_path = Path(args.config)
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file {config_path} does not exist")

    with open(config_path, "r") as file:
        config_data = yaml.safe_load(file)
    ptah_config = PtahConfig.model_validate(config_data)

    BUILDERS_PATH = ptah_config.global_settings.builders_path
    GIT_REPO_PATH = ptah_config.global_settings.git_repo_path
    OUTPUT_PATH = ptah_config.global_settings.output_path
    OPENWRT_BASE_RELEASES_URL = ptah_config.global_settings.openwrt_base_releases_url
    OPENWRT_BUILDER_FILE_EXT = ptah_config.global_settings.openwrt_builder_file_ext

    SECRETS = get_secrets(ptah_config.credentials)

    main(ptah_config)
