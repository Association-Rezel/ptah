from typing import List, Optional
from pydantic import BaseModel


class CertificateData(BaseModel):
    ca_chain: List[str]
    certificate: str
    expiration: int
    issuing_ca: str
    private_key: str
    private_key_type: str
    serial_number: str


class VaultResponse(BaseModel):
    request_id: str
    lease_id: str
    renewable: bool
    lease_duration: int
    data: CertificateData
    wrap_info: Optional[dict]
    warnings: Optional[List[str]]
    auth: Optional[dict]
    mount_type: str
