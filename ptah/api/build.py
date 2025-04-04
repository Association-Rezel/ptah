from pathlib import Path
import subprocess
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from models.build import BuildRequest
from models.PtahConfig import PtahConfig, PtahProfile
from models.BuildCallObject import BuildCallObject
from models.RouterFilesOrganizer import RouterFilesOrganizer
from models.base import PortableMac
from utils.handle_router_specific_files import HandleRouterSpecificFiles
from utils.handle_shared_files import SharedFilesHandler
from utils.utils import mac_to_filename_compliant, recreate_dir
from .dependencies import get_config, read_secrets
from shutil import move

router = APIRouter()


def check_profile_exists(profile: str, config: PtahConfig) -> PtahProfile:
    for ptah_profile in config.ptah_profiles:
        if ptah_profile.name == profile:
            return ptah_profile
    return None


def run_make_build(profile: PtahProfile, config: PtahConfig, mac: str) -> bool:
    packages = " ".join(profile.packages) if profile.packages else ""
    make_image_cmd = (
        f"make image "
        f'PROFILE="{profile.openwrt_profile.name}" '
        f'PACKAGES="{packages}" '
        f'EXTRA_IMAGE_NAME="ptah-{mac}" '
        f'BIN_DIR="{config.global_settings.output_path / mac}" '
        f'FILES="{config.global_settings.routers_files_path / mac }" '
    )
    profile = config.global_settings.builders_path / profile.name
    with open(profile / "builder_folder") as f:
        builder_name = f.readline().strip("\n")
    builder_path = config.global_settings.builders_path / profile.name / builder_name

    recreate_dir(config.global_settings.output_path / mac)

    try:
        subprocess.run(make_image_cmd, shell=True, check=True, cwd=builder_path)
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Build failed.",
        )
        return False
    return True


@router.post("/build")
def build_endpoint(
    request: BuildRequest,
    config: PtahConfig = Depends(get_config),
    secrets: dict = Depends(read_secrets),
):
    mac = request.mac
    mac_fc = mac.filename_compliant()
    if (ptah_profile := check_profile_exists(request.profile, config)) is None:
        return {"error": "Profile not found"}, 404

    router_files = RouterFilesOrganizer(
        mac=mac,
        global_settings=config.global_settings,
    )

    bao = BuildCallObject(
        mac=mac,
        profile=ptah_profile,
        global_settings=config.global_settings,
        secrets=secrets,
        versions=[],
        router_files=router_files,
    )
    files_dest_path = Path(config.global_settings.routers_files_path / mac_fc)
    recreate_dir(files_dest_path)
    sfh = SharedFilesHandler(bao)

    hrsf = HandleRouterSpecificFiles(bao)
    sfh.handle_shared_files()
    hrsf.handle_router_specific_files()

    router_files.merge_files_to_router_files()

    run_make_build(
        ptah_profile,
        config,
        mac_fc,
    )
    binary_name = ptah_profile.openwrt_profile.get_generated_binary_name(mac_fc)
    binary_path = config.global_settings.output_path / mac_fc / binary_name
    if not binary_path.exists():
        return HTTPException(
            status_code=500,
            detail=f"Build failed.",
        )

    move(binary_path, config.global_settings.output_path / mac_fc / "ptah.bin")

    return JSONResponse(
        content={
            "message": "Build completed successfully.",
            "mac": mac,
            "ptah_version_hash": bao.final_version,
            "download_url": f"/build/download/{mac}",
        },
        status_code=200,
    )


@router.get("/build/download/{mac}")
def download_build_endpoint(
    mac: PortableMac,
    config: PtahConfig = Depends(get_config),
):
    mac_fc = mac.filename_compliant()
    binary_name = f"ptah.bin"
    binary_path = config.global_settings.output_path / mac_fc / binary_name
    if not binary_path.exists():
        raise HTTPException(
            status_code=404,
            detail="File not found",
        )
    return FileResponse(
        path=binary_path,
        filename=binary_name,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={binary_name}",
        },
    )
