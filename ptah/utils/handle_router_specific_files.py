from pathlib import Path

from contexts import BuildContext
from models import PathTransferHandler
from utils.utils import echo_to_file, recreate_dir


class RouterSpecificFilesHandler:
    def __init__(self, build_context: BuildContext):
        self.build_context = build_context

    def handle_router_specific_files(self):
        """
        Handle files that are specific to a router, including vault certs and versioning.
        """
        router_temp_dir = (
            self.build_context.global_settings.router_temporary_path
            / self.build_context.mac.to_filename_compliant()
        )

        # Ensure a clean temporary directory for the router files
        recreate_dir(router_temp_dir)

        router_files_config = self.build_context.profile.files.router_specific_files
        if not router_files_config:
            return

        if router_files_config.vault_certificates:
            print("Handling vault certificates")  # Placeholder for future logic

        # Compute and store the version hash
        self.build_context.final_version = self.build_context.versions.compute_versions_hash()

        version_file_path = router_temp_dir / "ptah_version"
        echo_to_file(version_file_path, self.build_context.final_version)

        # Add version file to router's file transfer list
        self.build_context.router_files.file_transfer_entries.append(
            PathTransferHandler(
                source=version_file_path,
                dest=Path("/etc/ptah_version"),
            )
        )
