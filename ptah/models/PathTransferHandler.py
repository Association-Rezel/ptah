from pathlib import Path


class PathTransferHandler:
    source: Path
    dest: Path

    def __init__(self, source: Path, dest: Path):
        self.source = source
        self.dest = dest
