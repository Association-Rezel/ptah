# Written by: Nathan Roos
"""
Define a class to manage JWT tokens
(we don't use a dedicated library like PyJwt because
the signing part is handled by the transit secret engine of Vault)
"""

import base64
from ast import literal_eval
import json
from pydantic import HttpUrl
import requests


class JwtTransitManager:
    """Provides methods to issue, verify and decode JWT tokens"""

    ALG: str = "RS256"
    SIGN_ALG: str = "pkcs1v15"

    def __init__(
        self,
        vault_token: str,
        vault_base_url: HttpUrl,
        transit_mount: str,
        transit_key: str,
    ) -> None:
        self.vault_base_url = vault_base_url
        self.transit_mount = transit_mount
        self.transit_key = transit_key

        # headers for the requests to Vault
        self.headers = {
            "X-Vault-Token": vault_token,
        }
        self.default_timeout = 9999999

        # headers for the JWT tokens
        self.jwt_headers = {"alg": self.ALG, "typ": "JWT"}
        self.base64_jwt_headers = self.encode_part(self.jwt_headers)

    def issue_jwt(self, payload: dict) -> str:
        """
        Issues a JWT signed by Vault.

        Args:
            payload (dict): The payload to be included in the JWT.

        Returns:
            str: The issued JWT.

        Raises:
            ConnectionError : if Vault is unreachable
            ValueError: If the request to sign the token fails.

        """
        base64_payload = self.encode_part(payload)
        jwt_input = self.base64_jwt_headers + "." + base64_payload
        base64_input = self.str_to_base64(jwt_input)

        # here a ConnectionError can be raised
        url = f"{self.vault_base_url}/v1/{self.transit_mount}/sign/{self.transit_key}"
        response = requests.post(
            url=url,
            headers=self.headers,
            data={
                "input": base64_input,
                "prehashed": False,
                "signature_algorithm": self.SIGN_ALG,
            },
            timeout=self.default_timeout,
        )

        if response.status_code == 200:
            signature: str = response.json()["data"]["signature"]
        else:
            raise ValueError(
                f"Failed to sign token. Status code: {response.status_code}\
                            response: {response.json()}"
            )
        raw_sig = signature.replace("vault:v1:", "")
        jwt_signature = self.base64_to_base64url(raw_sig)
        return f"{jwt_input}.{jwt_signature}"

    def verify_jwt(self, jwt: str) -> bool:
        """Check whether the signature of the token matches its content.

        Args:
            jwt (str): The JWT token to verify, ex : "header.payload.signature"

        Returns:
            bool: True if the token is valid, False otherwise.

        Raises :
        * ConnectionError : raised if Vault is unreachable
        * ValueError : if the request failed for another reason
        """
        try:
            header, payload, signature = jwt.split(".")
        except ValueError:
            return False

        # check if the header is valid
        base64_input = self.str_to_base64(f"{header}.{payload}")
        base64_signature = self.base64url_to_base64(signature)

        # here a ConnectionError can be raised
        url = f"{self.vault_base_url}/v1/{self.transit_mount}/verify/{self.transit_key}"
        response = requests.post(
            url=url,
            headers=self.headers,
            data={
                "input": base64_input,
                "signature": "vault:v1:" + base64_signature,
                "prehashed": False,
                "signature_algorithm": self.SIGN_ALG,
            },
            timeout=self.default_timeout,
        )

        # check response status
        if response.status_code == 200:
            return bool(response.json()["data"]["valid"])
        else:
            raise ValueError(
                f"Request to verify token failed. "
                f"Status code: {response.status_code} "
                f"Content: {response.json()}"
            )

    def decode_jwt(self, jwt: str) -> dict:
        """Return the payload as a dict."""
        try:
            _, base64_payload, _ = jwt.split(".")
            # Add missing padding if needed
            padding_needed = 4 - (len(base64_payload) % 4)
            if padding_needed and padding_needed != 4:
                base64_payload += "=" * padding_needed
            decoded_bytes = base64.urlsafe_b64decode(base64_payload)
            return json.loads(decoded_bytes.decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Failed to decode JWT payload: {e}")

    def str_to_base64(self, txt: str) -> str:
        """Return a base64 encoded string"""
        return base64.b64encode(bytes(txt, "utf-8")).decode("utf-8")

    def base64url_encode(self, data: bytes) -> str:
        """Base64 URL encode without padding."""
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

    def base64_to_base64url(self, b64_sig: str) -> str:
        """Convert standard base64 to base64url without padding."""
        decoded = base64.b64decode(b64_sig)
        return self.base64url_encode(decoded)

    def base64url_to_base64(self, b64url_str: str) -> bytes:
        """Decode base64url string (without padding) to raw bytes."""
        padding_needed = 4 - (len(b64url_str) % 4)
        b64url_str += "=" * padding_needed if padding_needed != 4 else ""
        raw_bytes = base64.urlsafe_b64decode(b64url_str)
        return base64.b64encode(raw_bytes).decode("utf-8")

    def encode_part(self, part: dict) -> str:
        """Encode a part of the JWT (header or payload)."""
        return self.base64url_encode(
            json.dumps(part, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
