import re
from pydantic import BaseModel
from .PortableMac import PortableMac


class BuildRequest(BaseModel):
    profile: str
    mac: PortableMac


class DownloadBuildRequest(BaseModel):
    mac: PortableMac
