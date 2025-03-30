import argparse
import yaml
from pathlib import Path
from shutil import rmtree
from dotenv import load_dotenv
from models.PtahConfig import *
from utils.utils import (
    extract_tar_zst,
    load_ptah_config,
    recreate_dir,
    echo_to_file,
    clone_git_repo,
    get_secrets,
)
import requests

class PrepareDockerEnvironment:
    BUILDERS_PATH: Path
    GIT_REPO_PATH: Path
    OUTPUT_PATH: Path
    OPENWRT_BASE_RELEASES_URL: str
    OPENWRT_BUILDER_FILE_EXT: str
    SECRETS: dict

    ptah_config: PtahConfig
    
    def __init__(self, config: str):
        config_path = Path(config)
        self.ptah_config = load_ptah_config(config_path)

        self.BUILDERS_PATH = self.ptah_config.global_settings.builders_path
        self.GIT_REPO_PATH = self.ptah_config.global_settings.git_repo_path
        self.OUTPUT_PATH = self.ptah_config.global_settings.output_path
        self.OPENWRT_BASE_RELEASES_URL = self.ptah_config.global_settings.openwrt_base_releases_url
        self.OPENWRT_BUILDER_FILE_EXT = self.ptah_config.global_settings.openwrt_builder_file_ext

        self.SECRETS = get_secrets(self.ptah_config.credentials)

        
    # ------------------------------- Helper Functions ------------------------------ #


    def handle_git_for_profile(self, file: FileEntry):
        username = self.SECRETS[file.git.credentials.username_credential]
        password = self.SECRETS[file.git.credentials.password_credential]
        clone_git_repo(file, self.GIT_REPO_PATH / f"{file.name}", username, password)

    def handle_files_for_profile(self, file: FileEntry):
        if file.type == "git":
            self.handle_git_for_profile(file)
        elif file.type == "local":
            raise NotImplementedError("Local file handling not implemented yet")
        else:
            raise ValueError(f"Invalid file type: {file.type}")

    def fetch_openwrt_image_builder(
        self, profile: PtahProfile, profile_path: Path, tmp_path: Path
    ):
        openwrt_version = profile.openwrt_profile.openwrt_version
        target = profile.openwrt_profile.target
        arch = profile.openwrt_profile.arch
        target_url = f"{self.OPENWRT_BASE_RELEASES_URL}/{openwrt_version}/targets/{target}/{arch}"
        archive_name = f"openwrt-imagebuilder-{openwrt_version}-{target}-{arch}{self.OPENWRT_BUILDER_FILE_EXT}"
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
        echo_to_file(profile_path / "builder_folder", f"{archive_extracted_path}")
        

    # ---------------------------------- Main Logic --------------------------------- #
    def main(self):
        for path in [self.GIT_REPO_PATH, self.BUILDERS_PATH, self.OUTPUT_PATH]:
            recreate_dir(path)

        for profile in self.ptah_config.ptah_profiles:
            profile_path = self.BUILDERS_PATH / profile.name
            tmp_path = profile_path / "tmp"
            for path in [profile_path, tmp_path]:
                recreate_dir(path)

            for file in profile.files.profile_shared_files:
                self.handle_files_for_profile(file)

            self.fetch_openwrt_image_builder(profile, profile_path, tmp_path)
            rmtree(tmp_path)


# --------------------------------- Entry Point --------------------------------- #
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ptah Configuration Processor")
    parser.add_argument("--config", required=True, help="Path to Ptah configuration file")
    parser.add_argument("--docker-secrets-mount", help="Docker source file for secrets")
    args = parser.parse_args()

    if not args.docker_secrets_mount:
        raise ValueError("Please provide the source of the secrets")


    if not args.config:
        raise ValueError("Please provide path to configuration file")
    load_dotenv(args.docker_secrets_mount)

    PrepareDockerEnvironment(args.config).main()

