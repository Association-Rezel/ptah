from pathlib import Path
from models.PtahConfig import GlobalSettings, PtahProfile
from hashlib import sha256

from models.RouterFilesOrganizer import RouterFilesOrganizer
from models.base import PortableMac


class BuildCallObject:
    mac: PortableMac
    profile: PtahProfile
    global_settings: GlobalSettings
    versions: list
    secrets: dict
    router_files: RouterFilesOrganizer
    final_version: str

    def __init__(
        self,
        mac: PortableMac,
        profile: PtahProfile,
        global_settings: GlobalSettings,
        secrets: dict,
        versions: list,
        router_files: RouterFilesOrganizer,
    ):
        self.mac = mac
        self.profile = profile
        self.global_settings = global_settings
        self.secrets = secrets
        self.versions = versions
        self.router_files = router_files

    def compute_versions_hash(self):
        """
        Compute the hash of the versions list.
        """
        versions_str = "".join(self.versions)
        return sha256(versions_str.encode()).hexdigest()
