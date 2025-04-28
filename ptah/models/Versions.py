import hashlib
import json
from ptah.models.PtahConfig import PtahProfile


class Versions:
    _versions: list[str] = []
    profile: PtahProfile

    def __init__(self, profile: PtahProfile):
        self.profile = profile
        self._versions = []
        self._versions.append(
            hashlib.sha256(
                json.dumps(profile.model_dump_json()).encode("utf-8")
            ).hexdigest()
        )
        self._versions.append(profile.openwrt_profile.openwrt_version)

    def compute_versions_hash(self):
        """
        Compute the hash of the versions list.
        """
        print(self._versions)
        _hash = hashlib.sha256()
        for version in self._versions:
            _hash.update(version.encode("utf-8"))
        return _hash.hexdigest()
