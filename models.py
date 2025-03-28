from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, HttpUrl


# Git credentials embedded in file entry
class GitCredentialsReference(BaseModel):
    username_environ: str
    password_environ: str


class GitRepo(BaseModel):
    url: str
    type: Literal["http", "ssh", "git"]
    credentials: GitCredentialsReference


class FileEntry(BaseModel):
    type: Literal["local", "git"]
    path: str
    git: Optional[GitRepo] = None


class VaultCertificates(BaseModel):
    destination: str
    vault_server: HttpUrl
    pki_mount: str
    pki_role: str
    pki_ttl: str


class HostSpecificFiles(BaseModel):
    vault_certificates: Optional[VaultCertificates] = None


class Files(BaseModel):
    common_files: List[FileEntry]
    host_specific_files: HostSpecificFiles


class Profile(BaseModel):
    name: str
    target: str
    arch: str
    files: Files
    packages: List[str]


# Global credentials object
class Credential(BaseModel):
    source: Literal["environ"]


class PtahConfig(BaseModel):
    profiles: List[Profile]
    credentials: Dict[str, Credential]
