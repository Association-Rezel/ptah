from pathlib import Path
from typing import List

from pydantic import HttpUrl
import requests
from models.PtahConfig import FileEntry, GitlabRelease
from models.BuildCallObject import BuildCallObject
import zipfile
import re

from models.RouterFilesOrganizer import RouterFilesOrganizerFile


def get_gitlab_url(url: HttpUrl, token: str) -> requests.Response:
    return requests.get(url, headers={"PRIVATE-TOKEN": token})


def get_release_info(url: HttpUrl, token: str) -> dict:
    """
    Get release information from a GitLab URL.
    """
    response = get_gitlab_url(url, token)
    if response.status_code == 200:
        return response.json()
    else:
        raise ValueError(f"Failed to fetch release information: {response.status_code}")


def download_asset(asset_url: HttpUrl, destination: Path, token: str):
    headers = {"Authorization": f"Bearer {token}"}
    with requests.get(asset_url, headers=headers, stream=True) as response:
        if response.status_code == 200:
            filname_re = r"^.*filename=\"([^\"]+)\".*$"
            filename = re.search(
                filname_re, response.headers["Content-Disposition"]
            ).group(1)
            destination = destination / filename
            with open(destination, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        else:
            raise ValueError(f"Failed to download asset: {response.status_code}")
    return filename


def download_release_files(
    gitlab_release: GitlabRelease,
    gitlab_release_info: dict,
    token: str,
    destination: Path,
) -> None:
    if gitlab_release.assets:
        links = gitlab_release_info["assets"]["links"]
        available_assets = {}
        for link in links:
            available_assets[link["name"]] = link["url"]
        for asset in gitlab_release.assets:
            if not asset.name in available_assets.keys():
                raise ValueError(f"Asset {asset.name} not found in release.")
            asset_url = available_assets[asset.name]
            download_asset(
                asset_url,
                destination,
                token,
            )

    if gitlab_release.source:
        sources = gitlab_release_info["assets"]["sources"]
        available_sources = {}
        for source in sources:
            available_sources[source["format"]] = source["url"]
        if not "zip" in available_sources.keys():
            raise ValueError("Source zip file not found in release.")
        source_url = available_sources["zip"]
        downloaded_filename = download_asset(
            source_url,
            destination,
            token,
        )
        unzip_path = destination
        unzip_path.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination / downloaded_filename, "r") as zip_ref:
            zip_ref.extractall(unzip_path)

        source_folder = destination / (Path(downloaded_filename).stem)
        source_folder.rename(destination / "source")


class SharedFilesHandler:
    bao: BuildCallObject

    def __init__(self, build_call_object: BuildCallObject):
        self.bao = build_call_object

    def handle_gitlab_release(self, file: FileEntry):
        """
        Handle GitLab release files.
        """
        token = self.bao.secrets[file.gitlab_release.credentials.token]
        if not file.gitlab_release:
            raise ValueError("GitLab release information is missing.")

        gitlab_release_info = get_release_info(file.gitlab_release.release_url, token)

        tag_name = gitlab_release_info["tag_name"]

        self.bao.versions.append(f"{file.name}{tag_name}")

        release_files_path = Path(
            self.bao.global_settings.gitlab_releases_output_path / file.name / tag_name
        )
        if not release_files_path.is_dir():
            release_files_path.mkdir(parents=True, exist_ok=True)
            download_release_files(
                file.gitlab_release,
                gitlab_release_info,
                token,
                release_files_path,
            )
        release_dir_content = [
            _file.name for _file in list(release_files_path.iterdir())
        ]
        if file.gitlab_release.assets:
            for asset in file.gitlab_release.assets:
                if asset.name not in release_dir_content:
                    raise ValueError(f"Asset {asset.name} not found in files.")
                src_asset_path = release_files_path / asset.name
                dest_asset_path = asset.destination
                self.bao.router_files.files.append(
                    RouterFilesOrganizerFile(
                        source=src_asset_path,
                        dest=dest_asset_path,
                    )
                )
        if file.gitlab_release.source:
            for source in file.gitlab_release.source.paths:
                src_source_path = Path(release_files_path / "source" / source)
                if not src_source_path.is_dir():
                    raise ValueError(f"Source {source} not found in release.")
                self.bao.router_files.files.append(
                    RouterFilesOrganizerFile(
                        source=src_source_path,
                        dest=Path("/"),
                    )
                )

    def handle_shared_files(self):
        """
        Handle shared files for a given profile.
        """
        for file in self.bao.profile.files.profile_shared_files:
            if file.type == "git":
                raise NotImplementedError("Git Repo handling not implemented yet")
            elif file.type == "local":
                raise NotImplementedError("Local file handling not implemented yet")
            elif file.type == "gitlab_release":
                self.handle_gitlab_release(file)
            else:
                raise ValueError(f"Invalid file type: {file.type}")
