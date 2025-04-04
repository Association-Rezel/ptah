from typing import Dict
from contexts import BuildContext
from models import PortableMac


class AppContext:
    def __init__(self):
        self.build_contexts: Dict[PortableMac, BuildContext] = {}
