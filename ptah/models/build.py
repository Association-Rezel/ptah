from pydantic import BaseModel


class BuildPrepareRequest(BaseModel):
    profile: str
