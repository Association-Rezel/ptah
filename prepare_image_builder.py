#!/bin/python3

import argparse
import os
import yaml
import git
from pathlib import Path
from shutil import rmtree, copytree, copy2
from dotenv import load_dotenv
from typing import Optional
from models import *
from packaging import version
import requests
import re
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


def build_git_http_url(url: str, username: str, password: str) -> str:
    protocol, rest = url.split("://", 1)
    return f"{protocol}://{username}:{password}@{rest}"


def recreate_dir(path: Path):
    if path.is_dir():
        rmtree(path)
    elif path.exists():
        print(f"Error: '{path}' exists and is not a directory.")
        os._exit(1)
    path.mkdir(parents=True, exist_ok=True)


def clone_git_repo(file: FileEntry, dest: Path):
    if file.git.type == "http":
        username = os.getenv(file.git.credentials.username_environ)
        password = os.getenv(file.git.credentials.password_environ)
        if not username or not password:
            print("Missing Git credentials in environment.")
            os._exit(1)
        url = build_git_http_url(file.git.url, username, password)
        git.Repo.clone_from(url, dest)
    elif file.git.type == "ssh":
        print("SSH not supported yet")
        os._exit(1)
    else:
        print("Unsupported Git type")
        os._exit(1)


def handle_files_for_profile(file: FileEntry, tmp_git_path: Path, output_path: Path):
    if file.type == "git":
        repo_name = Path(file.git.url).stem
        repo_path = tmp_git_path / f"{repo_name}"
        clone_git_repo(file, repo_path)
        src_path = repo_path / file.path
        dest_path = output_path / f"git_{repo_name}" / Path(file.path)
        copytree(src_path, dest_path)
    elif file.type == "local":
        src_path = Path(file.path)
        dest_path = output_path / f"local_{src_path.name}"
        copytree(src_path, dest_path)
    else:
        print(f"Invalid file type: {file.type}")
        os._exit(1)


def merge_tmp_to_files(tmp_path: Path, files_path: Path):
    for src_dir in tmp_path.iterdir():
        if src_dir.name == "git":
            continue  # Skip the git directory
        if not src_dir.is_dir():
            continue

        for root, _, files in os.walk(src_dir):
            root_path = Path(root)
            relative_path = root_path.relative_to(src_dir)
            dest_dir = files_path / relative_path
            dest_dir.mkdir(parents=True, exist_ok=True)

            for file in files:
                src_file = root_path / file
                dest_file = dest_dir / file
                copy2(src_file, dest_file)


def get_openwrt_latest_release():
    latest_release = sorted(
        re.findall(r"\d+\.\d+\.\d+", requests.get(OPENWRT_BASE_RELEASES_URL).text),
        key=version.parse,
    )[-1]
    return latest_release


def fetch_openwrt_image_builder(
    profile: Profile, openwrt_version: str, profile_path: Path, tmp_path: Path
):
    target_url = f"{OPENWRT_BASE_RELEASES_URL}/{openwrt_version}/targets/{profile.target}/{profile.arch}"
    archive_name = f"openwrt-imagebuilder-{openwrt_version}-{profile.target}-{profile.arch}.Linux-x86_64.tar.zst"
    image_builder_url = f"{target_url}/{archive_name}"
    response = requests.get(image_builder_url, stream=True)
    response.raise_for_status()

    archive_path = tmp_path / archive_name
    with open(archive_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    unpack_dir = profile_path / archive_path.stem
    unpack_dir.mkdir(parents=True, exist_ok=True)
    extract_tar_zst(archive_path, unpack_dir)


def echo_to_file(file: Path, content: str):
    with open(file, "w") as f:
        f.write(content)


def prepare_commands(
    profile: Profile,
    openwrt_version: str,
    ptah_version: Optional[str],
    profile_path: Path,
):
    # ------------------------ Get Vault VaultCertificates ----------------------- #
    if profile.files.host_specific_files.vault_certificates:
        vault_pki_mount = profile.files.host_specific_files.vault_certificates.pki_mount
        vault_pki_role = profile.files.host_specific_files.vault_certificates.pki_role
        vault_pki_ttl = profile.files.host_specific_files.vault_certificates.pki_ttl
        vault_server = profile.files.host_specific_files.vault_certificates.vault_server
        vault_cmd = f'VAULT_ADDR={vault_server} vault write {vault_pki_mount}/issue/{vault_pki_role} ttl="{vault_pki_ttl}"'
        echo_to_file(profile_path / "vault_certificates_cmd.sh", vault_cmd)

    # -------------------------------- make image -------------------------------- #
    packages = " ".join(profile.packages) if profile.packages else ""
    make_image_cmd = (
        f"make image "
        f'PROFILE="{profile.name}" '
        f'PACKAGES="{packages}" '
        f'EXTRA_IMAGE_NAME="ptah-{ptah_version if ptah_version else "no_version"}" '
        f'FILES="{profile_path / "files"}" '
        f'BUILD_DIR="{Path("/") / Path("bin")}"'
    )

    echo_to_file(profile_path / "make_image_cmd.sh", make_image_cmd)


# ---------------------------------- Main Logic --------------------------------- #
def main(
    config_path: Optional[Path], openwrt_version: str, ptah_version: Optional[str]
):
    load_dotenv()

    try:
        with open(config_path, "r") as file:
            config_data = yaml.safe_load(file)
        ptah_config = PtahConfig(**config_data)
    except Exception as e:
        print("Error loading configuration file:", e)
        os._exit(1)

    build_path = Path(BUILD_DIR)
    recreate_dir(build_path)

    for profile in ptah_config.profiles:
        profile_path = build_path / profile.name
        recreate_dir(profile_path)

        files_path = profile_path / "files"
        tmp_path = profile_path / "tmp"
        tmp_git_path = tmp_path / "git"

        for path in [files_path, tmp_path, tmp_git_path]:
            recreate_dir(path)

        for file in profile.files.common_files:
            handle_files_for_profile(file, tmp_git_path, tmp_path)

        merge_tmp_to_files(tmp_path, files_path)

        fetch_openwrt_image_builder(profile, openwrt_version, profile_path, tmp_path)

        prepare_commands(profile, openwrt_version, ptah_version, profile_path)
        
        rmtree(tmp_path)


# --------------------------------- Entry Point --------------------------------- #
if __name__ == "__main__":
    BUILD_DIR = "build"
    OPENWRT_BASE_RELEASES_URL = "https://downloads.openwrt.org/releases"
    OPENWRT_BUILDER_FILE_EXT = ".Linux-x86_64.tar.zst"

    parser = argparse.ArgumentParser(description="Ptah Configuration Processor")
    parser.add_argument(
        "--config", required=True, help="Path to Ptah configuration file"
    )
    parser.add_argument("--openwrt-version", help="OpenWRT version to build")

    parser.add_argument("--ptah-version", help="Ptah version to build")
    
    parser.add_argument("--output-dir", help="Output directory to store the build artifacts")

    parser.add_argument("--secrets-source", help="Tell what is the source of the secrets (env, file, etc.)")
    parser.add_argument(
        "--secrets-file", help="Path to the secrets file if using file as source"
    )

    args = parser.parse_args()

    # ------------------------------ Secrets sources ----------------------------- #
    SECRETS_SOURCE = args.secrets_source
    if not SECRETS_SOURCE:
        print("Please provide the source of the secrets")
        os._exit(1)
    if SECRETS_SOURCE == "file":
        if not args.secrets_file:
            print("Please provide the path to the secrets file")
            os._exit(1)

    load_dotenv(args.secrets_file) if SECRETS_SOURCE == "file" else None

    # ---------------------------------- Config ---------------------------------- #
    if not args.config:
        print("Please provide path to configuration file")
        os._exit(1)
    
    BUILD_DIR = args.output_dir if args.output_dir else BUILD_DIR

    if not args.openwrt_version:
        print(
            f"Please provide the OpenWRT version to build. Latest release: {get_openwrt_latest_release()}"
        )
        os._exit(1)

    main(Path(args.config), args.openwrt_version, args.ptah_version)
