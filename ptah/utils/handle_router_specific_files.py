import jwt
import requests

from pathlib import Path
from typing import cast
from rezel_vault_jwt.jwt_transit_manager import JwtTransitManager
from rezel_vault_jwt.jwt_payload_builder import JwtPayloadBuilder

from ptah.contexts import BuildContext
from ptah.env import ENV
from ptah.models import PathTransferHandler, SpecificFileEntry
from ptah.models import VaultResponse
from ptah.models.VaultResponses import CertificateData, PtahSecretsData
from ptah.utils.utils import build_url, echo_to_file, recreate_dir


class RouterSpecificFilesHandler:
    def __init__(self, build_context: BuildContext):
        self.build_context = build_context
        self.jwt_payload_builder = JwtPayloadBuilder()

    def handle_vault_certificates(
        self, file_entry: SpecificFileEntry, temporary_dir: Path
    ):
        """
        Handle vault certificates for the router.
        """
        if not file_entry.vault_certificates:
            raise ValueError("Vault certificates information is missing.")
        vault_certificates = file_entry.vault_certificates
        vault_pki_role_url = build_url(
            str(ENV.vault_url),
            "v1",
            vault_certificates.pki_mount,
            "issue",
            vault_certificates.pki_role,
        )

        vault_token = self.build_context.secrets[
            vault_certificates.credentials.vault_token
        ]
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
        request.raise_for_status()

        vault_cert_data = cast(
            CertificateData, VaultResponse.model_validate_json(request.text).data
        )
        cert_data = vault_cert_data.certificate
        key_data = vault_cert_data.private_key

        cert_file_name = "ptah_vault_ssl_mac.pem"
        key_file_name = "ptah_vault_ssl_mac.key"
        cert_files = [
            (cert_file_name, cert_data),
            (key_file_name, key_data),
        ]

        for filename, content in cert_files:
            temp_path = temporary_dir / filename
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(content)

            destination_path = Path(vault_certificates.destination) / filename

            self.build_context.router_files.file_transfer_entries.append(
                PathTransferHandler(source=temp_path, dest=destination_path)
            )

    def handle_jwt_from_vault_secrets(
        self,
        file_entry: SpecificFileEntry,
        temporary_dir: Path,
    ):
        """
        Handle JWT secrets from vault for the router.
        """
        if not file_entry.jwt_from_vault_secrets:
            raise ValueError("JWT from Vault secrets information is missing.")
        jwt_secrets = file_entry.jwt_from_vault_secrets
        vault_kv_path = build_url(
            str(ENV.vault_url),
            "v1",
            jwt_secrets.kv_mount,
            "data",
            jwt_secrets.kv_path,
        )
        vault_token = self.build_context.secrets[jwt_secrets.credentials.vault_token]

        request = requests.get(
            vault_kv_path,
            headers={"X-Vault-Token": vault_token},
            timeout=10,
        )
        request.raise_for_status()

        ptah_secrets_data = cast(
            PtahSecretsData,
            VaultResponse.model_validate_json(request.text).data.data,
        )
        jwt_secret = ptah_secrets_data.jwt_secret_1

        payload = self.jwt_payload_builder.create_ptah_payload(
            mac=self.build_context.mac
        )
        encoded = jwt.encode(payload, jwt_secret, algorithm="HS256")

        jwt_file_name = f"{file_entry.name}.jwt"
        temp_path = temporary_dir / jwt_file_name

        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(encoded)

        destination_path = Path(jwt_secrets.destination) / jwt_file_name

        self.build_context.router_files.file_transfer_entries.append(
            PathTransferHandler(source=temp_path, dest=destination_path)
        )

    def handle_jwt_from_vault_transit(
        self,
        file_entry: SpecificFileEntry,
        temporary_dir: Path,
    ):
        """
        Handle JWT secrets from vault for the router.
        """
        if not file_entry.jwt_from_vault_transit:
            raise ValueError("JWT from Vault secrets information is missing.")
        jwt_transit = file_entry.jwt_from_vault_transit
        vault_token = self.build_context.secrets[jwt_transit.credentials.vault_token]
        jwt_manager = JwtTransitManager(
            vault_token,
            ENV.vault_url,
            jwt_transit.transit_mount,
            jwt_transit.transit_key,
        )

        payload = self.jwt_payload_builder.create_ptah_payload(
            mac=self.build_context.mac
        )
        encoded = jwt_manager.issue_jwt(payload)

        jwt_file_name = f"{file_entry.name}.jwt"
        temp_path = temporary_dir / jwt_file_name
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(encoded)

        destination_path = Path(jwt_transit.destination) / jwt_file_name

        self.build_context.router_files.file_transfer_entries.append(
            PathTransferHandler(source=temp_path, dest=destination_path)
        )

    def handle_router_specific_files(self):
        """
        Handle files that are specific to a router, including vault certs and versioning.
        """
        router_temp_dir = (
            ENV.router_temporary_path / self.build_context.mac.to_filename_compliant()
        )

        recreate_dir(router_temp_dir)

        router_files_config = self.build_context.profile.files.router_specific_files
        if not router_files_config:
            return
        for file_entry in router_files_config:
            if file_entry.type == "vault_certificates":
                self.handle_vault_certificates(file_entry, router_temp_dir)
            elif file_entry.type == "jwt_from_vault_secrets":
                self.handle_jwt_from_vault_secrets(file_entry, router_temp_dir)
            elif file_entry.type == "jwt_from_vault_transit":
                self.handle_jwt_from_vault_transit(file_entry, router_temp_dir)
            else:
                raise ValueError(f"Unknown file entry type: {file_entry.type}")

        self.build_context.final_version = (
            self.build_context.versions.compute_versions_hash()
        )

        version_file_path = router_temp_dir / "ptah_version"
        echo_to_file(version_file_path, self.build_context.final_version)

        self.build_context.router_files.file_transfer_entries.append(
            PathTransferHandler(
                source=version_file_path,
                dest=Path("/etc/ptah_version"),
            )
        )
