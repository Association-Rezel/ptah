from pathlib import Path

import requests

from ptah.contexts import BuildContext
from ptah.models import PathTransferHandler, SpecificFileEntry
from ptah.models import VaultResponse
from ptah.utils.utils import echo_to_file, recreate_dir


class RouterSpecificFilesHandler:
    def __init__(self, build_context: BuildContext):
        self.build_context = build_context

    def handle_vault_certificates(
        self, file_entry: SpecificFileEntry, temporary_dir: Path
    ):
        """
        Handle vault certificates for the router.
        """
        if not file_entry.vault_certificates:
            raise ValueError("Vault certificates information is missing.")
        vault_certificates = file_entry.vault_certificates
        vault_pki_role_url = (
            f"{vault_certificates.vault_server}/v1/"
            f"{vault_certificates.pki_mount}"
            f"/issue/{vault_certificates.pki_role}"
        )
        vault_token = self.build_context.secrets[vault_certificates.credentials.token]
        cert_cn = f"{self.build_context.mac.to_filename_compliant()}{vault_certificates.cn_suffix}"

        request = requests.post(
            vault_pki_role_url,
            headers={"X-Vault-Token": vault_token},
            json={
                "common_name": cert_cn,
                "format": "pem",
            },
            timeout=10,
        )
        if request.status_code != 200:
            raise ValueError(
                f"Failed to retrieve certificate from Vault: {request.text}"
            )

        # Parsung vault response
        vault_response = VaultResponse.model_validate_json(request.text)
        cert_data = vault_response.data.certificate
        key_data = vault_response.data.private_key

        # Defining output file paths
        cert_file_name = "ptah_vault_ssl_mac.pem"
        key_file_name = "ptah_vault_ssl_mac.key"
        cert_files = [
            (cert_file_name, cert_data),
            (key_file_name, key_data),
        ]

        # Writing certificates to temp dir
        for filename, content in cert_files:
            temp_path = temporary_dir / filename
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(content)

            destination_path = Path(vault_certificates.destination) / filename

            self.build_context.router_files.file_transfer_entries.append(
                PathTransferHandler(source=temp_path, dest=destination_path)
            )

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
        for file_entry in router_files_config:
            if file_entry.type == "vault_certificates":
                self.handle_vault_certificates(file_entry, router_temp_dir)
            else:
                raise ValueError(f"Unknown file entry type: {file_entry.type}")

        # Compute and store the version hash
        self.build_context.final_version = (
            self.build_context.versions.compute_versions_hash()
        )

        version_file_path = router_temp_dir / "ptah_version"
        echo_to_file(version_file_path, self.build_context.final_version)

        # Add version file to router's file transfer list
        self.build_context.router_files.file_transfer_entries.append(
            PathTransferHandler(
                source=version_file_path,
                dest=Path("/etc/ptah_version"),
            )
        )
