import subprocess
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from models.build import BuildRequest
from models.PtahConfig import PtahConfig, PtahProfile
from utils.utils import mac_to_filename_compliant, recreate_dir
from .dependencies import get_config

router = APIRouter()

def check_profile_exists(profile: str, config: PtahConfig) -> bool:
    for ptah_profile in config.ptah_profiles:
        if ptah_profile.name == profile:
            return ptah_profile
    return False

def run_make_build(profile: PtahProfile, config: PtahConfig, mac: str) -> bool:
    packages  = " ".join(profile.packages) if profile.packages else ""
    make_image_cmd = (
        f"make image "
        f'PROFILE="{profile.openwrt_profile.name}" '
        f'PACKAGES="{packages}" '
        f'EXTRA_IMAGE_NAME="ptah-{mac}" '
        f'BIN_DIR="{config.global_settings.output_path / mac}" '
        f'FILES="{config.global_settings.builders_path / profile.name / "files"}" '
    )
    profile = config.global_settings.builders_path / profile.name
    with open(profile / "builder_folder") as f:
        builder_name = f.readline().strip('\n')
    builder_path = config.global_settings.builders_path / profile.name / builder_name

    recreate_dir(config.global_settings.output_path / mac)

    try:
        subprocess.run(make_image_cmd, shell=True, check=True, cwd=builder_path)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        return False
    return True

def build_binary_name(profile: PtahProfile, mac: str) -> str:
    binary_name = (
        f"openwrt-"
        f"{profile.openwrt_profile.openwrt_version}-"
        f"ptah-{mac}-"
        f"{profile.openwrt_profile.target}-"
        f"{profile.openwrt_profile.arch}-"
        f"{profile.openwrt_profile.name}-"
        f"squashfs-sysupgrade.bin"
    )
    return binary_name

@router.post("/build")
def build_endpoint(request: BuildRequest, config: PtahConfig = Depends(get_config)):
    mac = mac_to_filename_compliant(request.mac)
    if not (ptah_profile := check_profile_exists(request.profile, config)):
        return {"error": "Profile not found"}, 404
    if not run_make_build(ptah_profile, config, mac):
        return {"error": "Build failed"}, 500
    
    binary_name = build_binary_name(ptah_profile, mac)
    binary_path = config.global_settings.output_path / mac / binary_name
    if not binary_path.exists():
        return {"error": "Build failed"}, 500
    return FileResponse(
        path=binary_path,
        filename="ptah.bin",
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename=ptah.bin",
        },
    )

