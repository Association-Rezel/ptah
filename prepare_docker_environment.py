import argparse
from pathlib import Path
from shutil import rmtree
from ptah.env import ENV
from ptah.models.PtahConfig import PtahConfig, PtahProfile
from ptah.utils.utils import (
    extract_tar_zst,
    load_ptah_config,
    recreate_dir,
    echo_to_file,
)
import requests


class PrepareDockerEnvironment:
    ptah_config: PtahConfig

    def __init__(self, config: str):
        config_path = Path(config)
        self.ptah_config = load_ptah_config(config_path)

    # ------------------------------- Helper Functions ------------------------------ #

    def fetch_openwrt_image_builder(
        self, profile: PtahProfile, profile_path: Path, tmp_path: Path
    ):
        openwrt_version = profile.openwrt_profile.openwrt_version
        target = profile.openwrt_profile.target
        arch = profile.openwrt_profile.arch
        target_url = (
            f"{ENV.openwrt_base_releases_url}/{openwrt_version}/targets/{target}/{arch}"
        )
        archive_name = f"openwrt-imagebuilder-{openwrt_version}-{target}-{arch}{ENV.openwrt_builder_file_ext}"
        image_builder_url = f"{target_url}/{archive_name}"

        response = requests.get(image_builder_url, stream=True, timeout=40)
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
        for path in [
            ENV.git_repo_path,
            ENV.builders_path,
            ENV.output_path,
            ENV.gitlab_releases_output_path,
            ENV.routers_files_path,
        ]:
            recreate_dir(path)

        for profile in self.ptah_config.ptah_profiles:
            profile_path = ENV.builders_path / profile.name
            tmp_path = profile_path / "tmp"
            for path in [profile_path, tmp_path]:
                recreate_dir(path)

            self.fetch_openwrt_image_builder(profile, profile_path, tmp_path)
            rmtree(tmp_path)


# --------------------------------- Entry Point --------------------------------- #
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ptah Configuration Processor")
    parser.add_argument(
        "--config", required=True, help="Path to Ptah configuration file"
    )
    args = parser.parse_args()

    if not args.config:
        raise ValueError("Please provide path to configuration file")

    PrepareDockerEnvironment(args.config).main()
