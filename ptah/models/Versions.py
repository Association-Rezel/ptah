import hashlib
import json
from models.PtahConfig import PtahProfile


class Versions:
    _list: list[str] = []
    profile: PtahProfile

    def __init__(self, profile: PtahProfile):
        self.profile = profile
        self._list = []
        self._list.append(
            hashlib.sha256(json.dumps(profile)).hexdigest().encode("utf-8")
        )
        self._list.append(profile.openwrt_profile.openwrt_version)

    def hash(self):
        """
        Compute the hash of the versions list.
        """
        print(self._list)
        hash = hashlib.sha256()
        for item in self._list:
            hash.update(item.encode("utf-8"))
        return hash.hexdigest()
