import os
from pathlib import Path
import re
from shutil import copy2

from ptah.env import ENV
from ptah.models import PortableMac
from ptah.models import PathTransferHandler
from ptah.utils.utils import recreate_dir


def process_ptah_permissions_on_folder(
    source_path: Path,
    destination_path: Path,
) -> None:
    permission_file = source_path / ".ptah_permissions"
    if not permission_file.exists():
        return
    with open(permission_file, "r", encoding="utf-8") as f:
        permissions = f.readlines()

    permission_regex = (
        r"^\s*(?!#)(?P<octal>[0-7]{3})\s+(?P<path>(?!/|\./|\.\./)[^\s#]+)$"
    )
    for line in permissions:
        match = re.match(permission_regex, line)
        if match:
            octal = match.group("octal")
            path = match.group("path")
            destination_file = destination_path / str(path)
            destination_file.chmod(int(octal, 8))


class RouterFilesOrganizer:
    mac: PortableMac
    file_transfer_entries: list[PathTransferHandler]

    def __init__(self, mac: PortableMac):
        self.mac = mac
        self.file_transfer_entries = []

    # This method organizes and copies the router files:
    # - Iterates over all files that the router needs.
    # - If a file is a directory, merges its contents.
    # - If a file is a regular file, it copies it.
    def merge_files_to_router_files(self):
        router_directory = (
            ENV.routers_files_path / self.mac.to_filename_compliant()
        )
        recreate_dir(router_directory)

        for file_handler in self.file_transfer_entries:
            source_path = file_handler.source
            if source_path.is_file():
                destination_path = router_directory / file_handler.dest.relative_to("/")
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                copy2(source_path, destination_path)
                if not file_handler.permission:
                    permission = int("644", 8)
                else:
                    permission = int(file_handler.permission, 8)
                destination_path.chmod(permission)
                continue

            # If it's a directory, recursively copy its contents
            for root, _, files in os.walk(source_path):
                root_directory_path = Path(root)
                relative_path = root_directory_path.relative_to(source_path)
                destination_subdir = router_directory / relative_path
                destination_subdir.mkdir(parents=True, exist_ok=True)

                for file in files:
                    source_file = root_directory_path / file
                    destination_file = destination_subdir / file
                    copy2(source_file, destination_file)
            process_ptah_permissions_on_folder(
                source_path=source_path,
                destination_path=router_directory,
            )
