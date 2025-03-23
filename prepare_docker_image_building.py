#!/bin/python3

import argparse
import os
import yaml
import git
from pathlib import Path
from shutil import rmtree, copytree, copy2
from dotenv import load_dotenv
from typing import List, Optional, Literal
from pydantic import BaseModel, HttpUrl


# ----------------------------- Configuration Models ---------------------------- #
class GitCredentials(BaseModel):
    username_environ: str
    password_environ: str


class GitRepo(BaseModel):
    url: str
    type: Literal["http", "ssh", "git"]
    credentials: GitCredentials


class FileEntry(BaseModel):
    type: Literal["local", "git"]
    path: str
    git: Optional[GitRepo] = None


class VaultCertificates(BaseModel):
    destination: str
    vault_server: HttpUrl
    pki_mount: str
    pki_role: str


class HostSpecificFiles(BaseModel):
    vault_certificates: VaultCertificates


class Files(BaseModel):
    common_files: List[FileEntry]
    host_specific_files: HostSpecificFiles


class Profile(BaseModel):
    name: str
    target: str
    arch: str
    files: Files


class PtahConfig(BaseModel):
    profiles: List[Profile]


# ------------------------------- Helper Functions ------------------------------ #
BUILD_DIR = "build"


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


def process_common_file(file: FileEntry, tmp_git_path: Path, output_path: Path):
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


# ---------------------------------- Main Logic --------------------------------- #
def main(config_path: Optional[Path]):
    load_dotenv()

    if not config_path:
        print("Please provide path to configuration file")
        os._exit(1)

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
            process_common_file(file, tmp_git_path, tmp_path)

        merge_tmp_to_files(tmp_path, files_path)


# --------------------------------- Entry Point --------------------------------- #
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ptah Configuration Processor")
    parser.add_argument(
        "--config", required=True, help="Path to Ptah configuration file"
    )
    args = parser.parse_args()

    main(Path(args.config))
