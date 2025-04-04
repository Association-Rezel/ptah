import re
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema
from typing import Annotated


def normalize_mac(mac: str) -> str:
    # Remove separators and lowercase
    clean = re.sub(r"[^0-9A-Fa-f]", "", mac).lower()
    if len(clean) != 12:
        raise ValueError(f"Invalid MAC address: {mac}")
    return ":".join(clean[i : i + 2] for i in range(0, 12, 2))


class PortableMac(str):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls.validate, core_schema.str_schema()
        )

    @classmethod
    def validate(cls, value: str) -> "PortableMac":
        if not isinstance(value, str):
            raise TypeError("MAC address must be a string")
        normalized = normalize_mac(value)
        return cls(normalized)

    # Placeholder method
    def filename_compliant(self):
        return self.replace(":", "-").replace("_", "-").replace(".", "_")
