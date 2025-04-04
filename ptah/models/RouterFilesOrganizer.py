import os
from pathlib import Path
from shutil import copy2

from pydantic import BaseModel

from models import GlobalSettings
from models import PortableMac
from models import PathTransferHandler
from utils.utils import recreate_dir

class RouterFilesOrganizer:
    mac: PortableMac
    global_settings: GlobalSettings
    file_transfer_entries: list[PathTransferHandler]

    def __init__(self, mac: PortableMac, global_settings: GlobalSettings):
        self.mac = mac
        self.global_settings = global_settings
        self.file_transfer_entries = []

    # This method organizes and copies the router files:
    # - Iterates over all files that the router needs.
    # - If a file is a directory, merges its contents.
    # - If a file is a regular file, it copies it.
    def merge_files_to_router_files(self):
        router_directory = self.global_settings.routers_files_path / self.mac.to_filename_compliant()
        recreate_dir(router_directory)

        for file_handler in self.file_transfer_entries:
            source_path = file_handler.source
            if source_path.is_file():
                destination_path = router_directory / file_handler.dest.relative_to("/")
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                copy2(source_path, destination_path)
                continue

            # If it's a directory, recursively copy its contents
            destination_directory = router_directory / file_handler.dest
            for root, _, files in os.walk(source_path):
                root_directory_path = Path(root)
                relative_path = root_directory_path.relative_to(source_path)
                destination_subdir = router_directory / relative_path
                destination_subdir.mkdir(parents=True, exist_ok=True)

                for file in files:
                    source_file = root_directory_path / file
                    destination_file = destination_subdir / file
                    copy2(source_file, destination_file)