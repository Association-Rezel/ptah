import hashlib
import json
from ptah.models.PtahConfig import PtahProfile


class Versions:
    versions: list[str] = []
    profile: PtahProfile

    def __init__(self, profile: PtahProfile):
        self.profile = profile
        self.versions = []
        self.versions.append(
            hashlib.sha256(
                json.dumps(profile.model_dump_json()).encode("utf-8")
            ).hexdigest()
        )
        self.versions.append(profile.openwrt_profile.openwrt_version)

    def compute_versions_hash(self):
        """
        Compute the hash of the versions list.
        """
        print(self.versions)
        _hash = hashlib.sha256()
        for version in self.versions:
            _hash.update(version.encode("utf-8"))
        return _hash.hexdigest()
