import logging
from pathlib import Path

import requests
import re
import zipfile

from pydantic import HttpUrl
from ptah.env import ENV
from ptah.models import FileEntry, GitlabRelease, PathTransferHandler
from ptah.contexts import BuildContext
from ptah.models.PtahConfig import GenericPackage
from ptah.utils.utils import build_url


def fetch_gitlab_api(
    url: HttpUrl, token: str, params: dict = None
) -> requests.Response:
    """Send GET request to GitLab API with token."""
    return requests.get(
        url, headers={"PRIVATE-TOKEN": token}, params=params, timeout=40
    )


def get_gitlab_release_info(release_url: HttpUrl, token: str) -> dict:
    """Retrieve release metadata from GitLab."""
    response = fetch_gitlab_api(release_url, token)
    if response.status_code == 200:
        return response.json()
    raise ValueError(f"Failed to fetch release information: {response.status_code}")


def extract_sha_from_filename(filename: str) -> str:
    """Extract SHA from a filename that contains it."""
    match = re.search(r"([a-f0-9]{40})", filename)
    if match:
        return match.group(1)
    raise ValueError("SHA not found in filename.")


def get_gitlab_generic_package_info(
    gitlab_url: HttpUrl,
    project_id: str,
    package_name: str,
    package_version: str,
    token: str,
) -> list:
    list_packages_api_url = build_url(
        str(gitlab_url), "api/v4/projects", project_id, "packages"
    )
    params = {"package_name": package_name, "package_type": "generic", "per_page": 100}
    response = fetch_gitlab_api(list_packages_api_url, token, params=params)
    if response.status_code != 200:
        raise ValueError(
            f"Failed to fetch package list for '{package_name}': {response.status_code}"
        )

    summary_package_info = None
    for package in response.json():
        if package.get("version") == package_version:
            summary_package_info = package
            break

    if not summary_package_info:
        raise ValueError(
            f"Package '{package_name}' with version '{package_version}' not found."
        )

    package_id = summary_package_info["id"]
    package_files_api_url = build_url(
        str(gitlab_url),
        "api/v4/projects",
        project_id,
        "packages",
        str(package_id),
        "package_files",
    )

    files_response = fetch_gitlab_api(package_files_api_url, token)
    if files_response.status_code != 200:
        raise ValueError(
            f"Failed to fetch files for package ID '{package_id}': {files_response.status_code}"
        )
    return files_response.json()


def download_gitlab_file(url: HttpUrl, download_dir: Path, token: str) -> str:
    """
    Download an asset from a GitLab release and save it to the specified directory.
    Returns the downloaded filename.
    """
    headers = {"Authorization": f"Bearer {token}"}
    with requests.get(url, headers=headers, stream=True, timeout=40) as response:
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


def get_gitlab_archive_filename(url: HttpUrl, token: str) -> str:
    headers = {"Authorization": f"Bearer {token}"}

    with requests.head(url, headers=headers, timeout=30) as response:
        response.raise_for_status()
        content_disposition = response.headers.get("Content-Disposition", "")
        match = re.search(r'filename="([^"]+)"', content_disposition)
        if not match:
            raise ValueError(
                "Filename could not be extracted from 'Content-Disposition' header."
            )
        filename = match.group(1)
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
            download_gitlab_file(asset_url_map[expected_asset.name], target_dir, token)

    if release_config.source:

        archive_url = build_url(
            str(release_config.gitlab_url),
            "api/v4/projects",
            release_config.project_id,
            "repository",
            "archive.zip",
        )

        zip_filename = download_gitlab_file(archive_url, target_dir, token)

        with zipfile.ZipFile(target_dir / zip_filename, "r") as zip_ref:
            zip_ref.extractall(target_dir)

        extracted_dir = target_dir / Path(zip_filename).stem
        extracted_dir.rename(target_dir / "source")


def download_gitlab_repo_archive(
    archive_url: HttpUrl,
    token: str,
    target_dir: Path,
) -> None:
    zip_filename = download_gitlab_file(archive_url, target_dir, token)

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

        self.build_context.versions._versions.append(f"{file_entry.name}{release_tag}")

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

    def handle_gitlab_repo_archive(self, file_entry: FileEntry):
        if not file_entry.gitlab_repo_archive:
            raise ValueError("GitLab repo archive information is missing.")

        token_name = file_entry.gitlab_repo_archive.credentials.token
        token = self.build_context.secrets[token_name]
        gitlab_repo_archive = file_entry.gitlab_repo_archive

        archive_url = build_url(
            str(gitlab_repo_archive.gitlab_url),
            "api/v4/projects",
            gitlab_repo_archive.project_id,
            "repository",
            "archive.zip?sha=" + gitlab_repo_archive.sha,
        )
        archive_commit_sha = extract_sha_from_filename(
            get_gitlab_archive_filename(archive_url, token)
        )

        repo_archive_output_dir = (
            Path(ENV.gitlab_releases_output_path) / file_entry.name / archive_commit_sha
        )

        if not repo_archive_output_dir.is_dir():
            repo_archive_output_dir.mkdir(parents=True, exist_ok=True)
            download_gitlab_repo_archive(
                archive_url,
                token,
                repo_archive_output_dir,
            )

        self.build_context.versions._versions.append(
            f"{file_entry.name}{archive_commit_sha}"
        )

        for source_path in file_entry.gitlab_repo_archive.source.paths:
            full_source_path = repo_archive_output_dir / "source" / source_path
            if not full_source_path.is_dir():
                raise ValueError(f"Source path '{source_path}' not found.")
            self.build_context.router_files.file_transfer_entries.append(
                PathTransferHandler(
                    source=full_source_path,
                    dest=Path("/"),
                )
            )

    def handle_gitlab_packages(self, file_entry: FileEntry):
        """Process GitLab generic packages-based file entry."""
        if not file_entry.gitlab_packages:
            raise ValueError("GitLab packages information is missing.")

        token_name = file_entry.gitlab_packages.credentials.token
        token = self.build_context.secrets[token_name]
        gitlab_packages_config = file_entry.gitlab_packages

        for generic_pkg in gitlab_packages_config.generic_packages:
            package_files_list = get_gitlab_generic_package_info(
                gitlab_packages_config.gitlab_url,
                gitlab_packages_config.project_id,
                generic_pkg.name,
                generic_pkg.version,
                token,
            )
            package_files_metadata = {f["file_name"]: f for f in package_files_list}
            for file_to_download in generic_pkg.files:
                if file_to_download.name not in package_files_metadata:
                    raise ValueError(
                        f"File '{file_to_download.name}' not found in package "
                        f"'{generic_pkg.name}' version '{generic_pkg.version}'."
                    )

                file_metadata = package_files_metadata[file_to_download.name]
                file_sha256 = str(file_metadata["file_sha256"])

                self.build_context.versions._versions.append(
                    f"{file_entry.name}:{generic_pkg.name}:{file_sha256}"
                )

                package_output_dir = (
                    ENV.gitlab_releases_output_path
                    / file_entry.name
                    / generic_pkg.name
                    / file_sha256
                )
                downloaded_file_path = package_output_dir / file_to_download.name

                if not downloaded_file_path.is_file():
                    package_output_dir.mkdir(parents=True, exist_ok=True)
                    download_url = build_url(
                        str(gitlab_packages_config.gitlab_url),
                        "api/v4/projects",
                        gitlab_packages_config.project_id,
                        "packages/generic",
                        generic_pkg.name,
                        generic_pkg.version,
                        file_to_download.name,
                    )
                    download_gitlab_file(download_url, package_output_dir, token)

                self.build_context.router_files.file_transfer_entries.append(
                    PathTransferHandler(
                        source=downloaded_file_path,
                        dest=file_to_download.destination,
                        permission=file_to_download.permission,
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
            elif file_entry.type == "gitlab_repo_archive":
                self.handle_gitlab_repo_archive(file_entry)
            elif file_entry.type == "gitlab_packages":
                self.handle_gitlab_packages(file_entry)
            else:
                raise ValueError(f"Unsupported file type: {file_entry.type}")
