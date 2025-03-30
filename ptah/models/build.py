import re
from pydantic import BaseModel
from .base import PortableMac

class BuildRequest(BaseModel):
    profile: str
    mac: PortableMac
