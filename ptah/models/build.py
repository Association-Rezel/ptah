import re
from pydantic import BaseModel
from .PortableMac import PortableMac


class BuildPrepareRequest(BaseModel):
    profile: str
