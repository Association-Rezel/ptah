from pathlib import Path

import requests
import re
import zipfile

from pydantic import HttpUrl
from ptah.env import ENV
from ptah.models import FileEntry, GitlabRelease, PathTransferHandler
from ptah.contexts import BuildContext
from ptah.utils.utils import build_url


def fetch_gitlab_api(url: HttpUrl, token: str) -> requests.Response:
    """Send GET request to GitLab API with token."""
    return requests.get(url, headers={"PRIVATE-TOKEN": token}, timeout=40)


def get_gitlab_release_info(release_url: HttpUrl, token: str) -> dict:
    """Retrieve release metadata from GitLab."""
    response = fetch_gitlab_api(release_url, token)
    if response.status_code == 200:
        return response.json()
    raise ValueError(f"Failed to fetch release information: {response.status_code}")


def download_asset_file(asset_url: HttpUrl, download_dir: Path, token: str) -> str:
    """
    Download an asset from a GitLab release and save it to the specified directory.
    Returns the downloaded filename.
    """
    headers = {"Authorization": f"Bearer {token}"}
    with requests.get(asset_url, headers=headers, stream=True, timeout=40) as response:
        response.raise_for_status()

        content_disposition = response.headers.get("Content-Disposition", "")
        match = re.search(r'^.*filename="([^"]+)".*$', content_disposition)
        if not match:
            raise ValueError("Filename could not be extracted from headers.")

        filename = match.group(1)
        file_path = download_dir / filename

        with open(file_path, "wb") as output_file:
            for chunk in response.iter_content(chunk_size=8192):
                output_file.write(chunk)

    return filename


def download_gitlab_release_files(
    release_config: GitlabRelease,
    release_info: dict,
    token: str,
    target_dir: Path,
) -> None:
    """Download assets and source from a GitLab release into target directory."""

    if release_config.assets:
        asset_links = release_info["assets"]["links"]
        asset_url_map = {link["name"]: link["url"] for link in asset_links}

        for expected_asset in release_config.assets:
            if expected_asset.name not in asset_url_map:
                raise ValueError(f"Asset '{expected_asset.name}' not found in release.")
            download_asset_file(asset_url_map[expected_asset.name], target_dir, token)

    if release_config.source:

        archive_url = build_url(
            str(release_config.gitlab_url),
            "api/v4/projects",
            release_config.project_id,
            "repository",
            "archive.zip",
        )

        zip_filename = download_asset_file(archive_url, target_dir, token)

        with zipfile.ZipFile(target_dir / zip_filename, "r") as zip_ref:
            zip_ref.extractall(target_dir)

        extracted_dir = target_dir / Path(zip_filename).stem
        extracted_dir.rename(target_dir / "source")


class SharedFilesHandler:
    def __init__(self, build_context: BuildContext):
        self.build_context = build_context

    def handle_gitlab_release_file(self, file_entry: FileEntry):
        """Process GitLab release-based file entry."""
        if not file_entry.gitlab_release:
            raise ValueError("GitLab release information is missing.")

        token_name = file_entry.gitlab_release.credentials.token
        token = self.build_context.secrets[token_name]
        gitlab_release = file_entry.gitlab_release
        release_url = build_url(
            str(gitlab_release.gitlab_url),
            "api/v4/projects",
            gitlab_release.project_id,
            "releases",
            gitlab_release.release_path,
        )
        release_info = get_gitlab_release_info(release_url, token)
        release_tag = str(release_info["tag_name"])

        self.build_context.versions.versions.append(f"{file_entry.name}{release_tag}")

        release_output_dir = (
            Path(ENV.gitlab_releases_output_path) / file_entry.name / release_tag
        )

        if not release_output_dir.is_dir():
            release_output_dir.mkdir(parents=True, exist_ok=True)
            download_gitlab_release_files(
                file_entry.gitlab_release,
                release_info,
                token,
                release_output_dir,
            )

        downloaded_files = {item.name for item in release_output_dir.iterdir()}

        if file_entry.gitlab_release.assets:
            for asset in file_entry.gitlab_release.assets:
                if asset.name not in downloaded_files:
                    raise ValueError(f"Expected asset '{asset.name}' not found.")
                self.build_context.router_files.file_transfer_entries.append(
                    PathTransferHandler(
                        source=release_output_dir / asset.name,
                        dest=asset.destination,
                        permission=asset.permission if asset.permission else "644",
                    )
                )

        if file_entry.gitlab_release.source:
            for source_path in file_entry.gitlab_release.source.paths:
                full_source_path = release_output_dir / "source" / source_path
                if not full_source_path.is_dir():
                    raise ValueError(f"Source path '{source_path}' not found.")
                self.build_context.router_files.file_transfer_entries.append(
                    PathTransferHandler(
                        source=full_source_path,
                        dest=Path("/"),
                    )
                )

    def handle_shared_files(self):
        """Handle all shared files in the current profile."""
        for file_entry in self.build_context.profile.files.profile_shared_files:
            if file_entry.type == "git":
                raise NotImplementedError(
                    "Git repository handling is not implemented yet."
                )
            elif file_entry.type == "local":
                raise NotImplementedError("Local file handling is not implemented yet.")
            elif file_entry.type == "gitlab_release":
                self.handle_gitlab_release_file(file_entry)
            else:
                raise ValueError(f"Unsupported file type: {file_entry.type}")
