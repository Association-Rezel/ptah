from pathlib import Path
from typing import List, Optional, Literal, Dict, Set, Union
from pydantic import BaseModel, HttpUrl, field_validator, model_validator


# Git credentials referenced from env vars
class GitCredentialsReference(BaseModel):
    username_credential: str
    password_credential: str


class GitRepo(BaseModel):
    url: HttpUrl
    type: Literal["http", "ssh", "git"]
    credentials: GitCredentialsReference


class Local(BaseModel):
    path: Path


class Asset(BaseModel):
    name: str
    destination: Path
    permission: str

    @field_validator("permission", mode="before")
    @classmethod
    def validate_permission(cls, v: str) -> str:
        if isinstance(v, int):
            v = str(v)
        if not v.isdigit() or len(v) not in {3, 4}:
            raise ValueError("Permission must be a 3 or 4 digit octal string")
        try:
            int(v, 8)
        except ValueError as exc:
            raise ValueError("Permission must be a valid octal number") from exc
        return v

    def permission_as_int(self) -> int:
        return int(self.permission, 8)


class Source(BaseModel):
    paths: List[Path]


class GitlabReleaseCredentialsReference(BaseModel):
    token: str


class GitlabRelease(BaseModel):
    gitlab_url: HttpUrl
    release_path: str
    project_id: Union[str, int]
    assets: Optional[List[Asset]] = None
    source: Optional[Source] = None
    credentials: GitlabReleaseCredentialsReference

    @field_validator("project_id", mode="before")
    @classmethod
    def cast_project_id_to_str(cls, v):
        return str(v)


class FileEntry(BaseModel):
    name: str
    type: Literal["gitlab_release"]
    gitlab_release: Optional[GitlabRelease] = None


class VaultCredentialsReference(BaseModel):
    vault_token: str


class VaultCertificates(BaseModel):
    destination: str
    pki_mount: str
    pki_role: str
    cn_suffix: str
    credentials: VaultCredentialsReference


class JwtFromVaultSecrets(BaseModel):
    destination: str
    kv_mount: str
    kv_path: str
    credentials: VaultCredentialsReference


class JwtFromVaultTransit(BaseModel):
    destination: str
    transit_mount: str
    transit_key: str
    credentials: VaultCredentialsReference


class SpecificFileEntry(BaseModel):
    name: str
    type: Literal[
        "vault_certificates", "jwt_from_vault_secrets", "jwt_from_vault_transit"
    ]
    vault_certificates: Optional[VaultCertificates] = None
    jwt_from_vault_secrets: Optional[JwtFromVaultSecrets] = None
    jwt_from_vault_transit: Optional[JwtFromVaultTransit] = None


class Files(BaseModel):
    profile_shared_files: List[FileEntry]
    router_specific_files: List[SpecificFileEntry]


class OpenWrtProfile(BaseModel):
    name: str
    target: str
    arch: str
    openwrt_version: str

    def get_imagebuilder_archive_name(self, openwrt_builder_file_ext) -> str:
        archive_name = (
            f"openwrt-imagebuilder-"
            f"{self.openwrt_version}-"
            f"{self.target}-"
            f"{self.arch}"
            f"{openwrt_builder_file_ext}"
        )
        return archive_name

    def get_generated_binary_name(self, mac: str) -> str:
        binary_name = (
            f"openwrt-"
            f"{self.openwrt_version}-"
            f"ptah-{mac}-"
            f"{self.target}-"
            f"{self.arch}-"
            f"{self.name}-"
            f"squashfs-sysupgrade.bin"
        )
        return binary_name


class PtahProfile(BaseModel):
    name: str
    openwrt_profile: OpenWrtProfile
    packages: Optional[List[str]] = None
    files: Files


class Credential(BaseModel):
    source: Optional[Literal["environ"]] = "environ"


class PtahConfig(BaseModel):
    ptah_profiles: List[PtahProfile]
    credentials: Optional[Dict[str, Optional[Credential]]] = None

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
            raise ValueError(
                f"These credentials are used but not declared: {', '.join(sorted(missing))}"
            )

        return self
