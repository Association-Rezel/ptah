from typing import Dict
from contexts import BuildContext
class AppContext:
    def __init__(self):
        self.context_dict: Dict[str, str] = {} 