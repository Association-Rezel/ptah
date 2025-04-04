from pathlib import Path
from models.PtahConfig import GlobalSettings, PtahProfile
from hashlib import sha256

from models import RouterFilesOrganizer
from models import PortableMac
from models import Versions


class BuildContext:
    mac: PortableMac
    profile: PtahProfile
    global_settings: GlobalSettings
    versions: Versions
    secrets: dict
    router_files: RouterFilesOrganizer
    final_version: str

    def __init__(
        self,
        mac: PortableMac,
        profile: PtahProfile,
        global_settings: GlobalSettings,
        secrets: dict,
        versions: Versions,
        router_files: RouterFilesOrganizer,
    ):
        self.mac = mac
        self.profile = profile
        self.global_settings = global_settings
        self.secrets = secrets
        self.versions = versions
        self.router_files = router_files

