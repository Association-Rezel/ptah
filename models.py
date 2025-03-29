from pathlib import Path
from typing import List, Optional, Literal, Dict, Set
from pydantic import BaseModel, HttpUrl, model_validator, root_validator


# Git credentials referenced from env vars
class GitCredentialsReference(BaseModel):
    username_credential: str
    password_credential: str


class GitRepo(BaseModel):
    url: HttpUrl
    type: Literal["http", "ssh", "git"]
    credentials: GitCredentialsReference


class FileEntry(BaseModel):
    name: Optional[str]  # Optional label for the file entry
    type: Literal["local", "git"]
    path: str
    git: Optional[GitRepo] = None


class VaultCertificates(BaseModel):
    destination: str
    vault_server: HttpUrl
    pki_mount: str
    pki_role: str
    pki_ttl: str


class RouterSpecificFiles(BaseModel):
    vault_certificates: Optional[VaultCertificates] = None


class Files(BaseModel):
    profile_shared_files: List[FileEntry]
    router_specific_files: RouterSpecificFiles


class OpenWrtProfile(BaseModel):
    name: str
    target: str
    arch: str
    openwrt_version: str


class PtahProfile(BaseModel):
    name: str
    openwrt_profile: OpenWrtProfile
    packages: Optional[List[str]]
    files: Files


class Credential(BaseModel):
    source: Optional[Literal["environ"]] = "environ"


class GlobalSettings(BaseModel):
    openwrt_base_releases_url: HttpUrl
    openwrt_builder_file_ext: str
    git_repo_path: Path
    builders_path: Path
    output_path: Path


class PtahConfig(BaseModel):
    ptah_profiles: List[PtahProfile]
    credentials: Optional[Dict[str, Optional[Credential]]] = None
    global_settings: GlobalSettings

    @model_validator(mode="before")
    @classmethod
    def populate_empty_credentials(cls, values):
        raw_credentials = values.get("credentials")
        if raw_credentials:
            for key, val in raw_credentials.items():
                # If val is None, treat it as {"source": "environ"}
                if val is None:
                    raw_credentials[key] = {"source": "environ"}
        return values

    @model_validator(mode="after")
    def validate_used_credentials_exist(self) -> "PtahConfig":
        declared = set(self.credentials.keys()) if self.credentials else set()
        used: Set[str] = set()

        for profile in self.ptah_profiles:
            for file in profile.files.profile_shared_files:
                if file.type == "git" and file.git:
                    used.add(file.git.credentials.username_credential)
                    used.add(file.git.credentials.password_credential)

        missing = used - declared
        if missing:
            raise ValueError(f"These credentials are used but not declared: {', '.join(sorted(missing))}")

        return self
