"""Environment definitions for the back-end."""

from os import getenv
from pathlib import Path
from dotenv import load_dotenv
from pydantic import HttpUrl
import requests

__all__ = ["EnvError", "ENV"]


class EnvError(OSError):
    """Any error related to environment variables."""


class MissingEnvError(EnvError):
    """An environment variable is missing."""

    def __init__(self, key: str) -> None:
        """An environment variable is missing."""
        super().__init__(f"{key} is not set")


def get_or_raise(key: str) -> str:
    """Get value from environment or raise an error."""
    value = getenv(key)
    if not value:
        raise MissingEnvError(key)
    return value


def get_or_none(key: str) -> str | None:
    """Get value from environment or return None."""
    value = getenv(key)
    if not value:
        return None
    return value


def get_or_default(key: str, default: str) -> str:
    """Get value from environment or return default."""
    value = getenv(key)
    if not value:
        return default
    return value


class Env:  # pylint: disable=too-many-instance-attributes
    """Check environment variables types and constraints."""

    deploy_env: str

    config_path: Path

    openwrt_base_releases_url: HttpUrl
    openwrt_builder_file_ext: str
    git_repo_path: Path
    builders_path: Path
    routers_files_path: Path
    output_path: Path
    gitlab_releases_output_path: Path
    router_temporary_path: Path

    vault_url: HttpUrl
    vault_role_name: str
    vault_transit_mount: str
    vault_transit_key: str

    def __init__(self) -> None:
        """Load all variables."""

        # If we are in a kubernetes pod, we need to load vault secrets and relevant .env file
        # Check if KUBERNETES_SERVICE_HOST is set
        if getenv("KUBERNETES_SERVICE_HOST"):
            load_dotenv("/vault/secrets/env")

        # Else, env variables are already loaded via docker compose
        self.deploy_env = get_or_default("DEPLOY_ENV", "local")
        load_dotenv(f".env.{self.deploy_env}")

        self.config_path = Path(
            get_or_default("PTAH_CONFIG_PATH", "/opt/ptah_config.yaml")
        )

        self.openwrt_base_releases_url = HttpUrl(
            get_or_default(
                "OPENWRT_BASE_RELEASES_URL",
                "https://downloads.openwrt.org/releases/",
            )
        )
        self.openwrt_builder_file_ext = get_or_default(
            "OPENWRT_BUILDER_FILE_EXT", ".Linux-x86_64.tar.zst"
        )

        self.git_repo_path = Path(get_or_default("GIT_REPO_PATH", "/opt/git"))
        self.builders_path = Path(get_or_default("BUILDERS_PATH", "/opt/builders"))
        self.routers_files_path = Path(
            get_or_default("ROUTERS_FILES_PATH", "/opt/routers_files")
        )
        self.output_path = Path(get_or_default("OUTPUT_PATH", "/opt/output"))
        self.gitlab_releases_output_path = Path(
            get_or_default("GITLAB_RELEASES_OUTPUT_PATH", "/opt/gitlab_releases")
        )
        self.router_temporary_path = Path(
            get_or_default("ROUTER_TEMPORARY_PATH", "/opt/temporary")
        )

        self.vault_url = HttpUrl(get_or_default("VAULT_URL", "http://vault:8200"))
        self.vault_role_name = get_or_none("VAULT_ROLE_NAME")
        self.vault_transit_mount = get_or_raise("VAULT_TRANSIT_MOUNT")
        self.vault_transit_key = get_or_raise("VAULT_TRANSIT_KEY")


ENV = Env()
