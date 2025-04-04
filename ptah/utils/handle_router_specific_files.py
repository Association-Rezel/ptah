from pathlib import Path
from models.BuildCallObject import BuildCallObject
from models.RouterFilesOrganizer import RouterFilesOrganizerFile
from utils.utils import echo_to_file, recreate_dir


class HandleRouterSpecificFiles:
    bao: BuildCallObject

    def __init__(self, bao: BuildCallObject):
        self.bao = bao

    def handle_router_specific_files(self):
        tmp_router_path = (
            self.bao.global_settings.router_temporary_path
            / self.bao.mac.filename_compliant()
        )
        recreate_dir(tmp_router_path)
        router_specific_files = self.bao.profile.files.router_specific_files
        if not router_specific_files:
            return
        if router_specific_files.vault_certificates:
            print("Handling vault certificates")

        # Compute version number
        self.bao.final_version = self.bao.compute_versions_hash()
        echo_to_file(tmp_router_path / "ptah_version", self.bao.final_version)
        self.bao.router_files.files.append(
            RouterFilesOrganizerFile(
                source=tmp_router_path / "ptah_version",
                dest=Path("/etc/ptah_version"),
            )
        )
