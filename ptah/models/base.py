# base.py
import re
from pydantic import BeforeValidator
from typing import Annotated

def normalize_mac(mac: str) -> str:
    # Remove separators and lowercase
    clean = re.sub(r'[^0-9A-Fa-f]', '', mac).lower()
    if len(clean) != 12:
        raise ValueError(f"Invalid MAC address: {mac}")
    return ':'.join(clean[i:i+2] for i in range(0, 12, 2))

def validate_mac(v):
    if not isinstance(v, str):
        raise TypeError("MAC address must be a string")
    return normalize_mac(v)

PortableMac = Annotated[str, BeforeValidator(validate_mac)]
