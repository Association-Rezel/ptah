from pathlib import Path
from typing import Optional


class PathTransferHandler:
    source: Path
    dest: Path
    permission: Optional[str] = None

    def __init__(self, source: Path, dest: Path, permission: str = None):
        self.source = source
        self.dest = dest
        self.permission = permission
