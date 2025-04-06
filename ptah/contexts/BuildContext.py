from ptah.models.PtahConfig import PtahProfile
from ptah.models import RouterFilesOrganizer
from ptah.models import PortableMac
from ptah.models import Versions


class BuildContext:
    mac: PortableMac
    profile: PtahProfile
    versions: Versions
    secrets: dict
    router_files: RouterFilesOrganizer
    final_version: str

    def __init__(
        self,
        mac: PortableMac,
        profile: PtahProfile,
        secrets: dict,
        versions: Versions,
        router_files: RouterFilesOrganizer,
    ):
        self.mac = mac
        self.profile = profile
        self.secrets = secrets
        self.versions = versions
        self.router_files = router_files
