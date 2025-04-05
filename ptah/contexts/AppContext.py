from typing import Dict
from ptah.contexts import BuildContext
from ptah.models import PortableMac


class AppContext:
    def __init__(self):
        self.build_contexts: Dict[PortableMac, BuildContext] = {}
