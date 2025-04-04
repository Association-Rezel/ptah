import os
from pathlib import Path
from shutil import copy2

from pydantic import BaseModel

from models.PtahConfig import GlobalSettings
from models.base import PortableMac
from utils.utils import recreate_dir


class RouterFilesOrganizerFile:
    source: Path
    dest: Path

    def __init__(self, source: Path, dest: Path):
        self.source = source
        self.dest = dest


class RouterFilesOrganizer:
    mac: PortableMac
    global_settings: GlobalSettings
    files: list[RouterFilesOrganizerFile]

    def __init__(self, mac: PortableMac, global_settings: GlobalSettings):
        self.mac = mac
        self.global_settings = global_settings
        self.files = []

    # We're copying all files that are wanted by the router
    # to the router root directory
    # First we iterate over the files wanted
    # Then if these files are directories merge them
    # /!\ Directories should be based on the root
    # If they are files copy them
    def merge_files_to_router_files(self):
        router_path = (
            self.global_settings.routers_files_path / self.mac.filename_compliant()
        )
        recreate_dir(router_path)
        for rfile in self.files:
            src_path = rfile.source
            if src_path.is_file():
                dest_path = router_path / rfile.dest.relative_to("/")
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                copy2(src_path, dest_path)
                continue
            dest_path = router_path / rfile.dest
            for root, _, files in os.walk(src_path):
                root_path = Path(root)
                relative_path = root_path.relative_to(src_path)
                dest_dir = router_path / relative_path
                dest_dir.mkdir(parents=True, exist_ok=True)
                for file in files:
                    src_file = root_path / file
                    dest_file = dest_dir / file
                    copy2(src_file, dest_file)
