from pathlib import Path
import subprocess
from typing import cast
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from models.build import BuildPrepareRequest
from models import PtahConfig, PtahProfile
from contexts import BuildContext, AppContext
from models import RouterFilesOrganizer
from models import PortableMac
from models import Versions
from utils.handle_router_specific_files import RouterSpecificFilesHandler
from utils.handle_shared_files import SharedFilesHandler
from utils.utils import recreate_dir
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


@router.post("/build/prepare/{mac}")
def build_endpoint(
    request: Request,
    mac: PortableMac,
    request_data: BuildPrepareRequest,
    config: PtahConfig = Depends(get_config),
    secrets: dict = Depends(read_secrets),
):
    ctx = cast(AppContext, request.app.state.ctx)
    build_contexts = ctx.build_contexts
    if not ctx:
        raise HTTPException(
            status_code=500,
            detail="Application context not initialized.",
        )

    mac_fc = mac.to_filename_compliant()
    if (ptah_profile := check_profile_exists(request_data.profile, config)) is None:
        return HTTPException(
            status_code=404,
            detail=f"Profile {request_data.profile} not found.",
        )

    router_files = RouterFilesOrganizer(
        mac=mac,
        global_settings=config.global_settings,
    )

    build_context = BuildContext(
        mac=mac,
        profile=ptah_profile,
        global_settings=config.global_settings,
        secrets=secrets,
        versions=Versions(ptah_profile),
        router_files=router_files,
    )
    build_contexts[mac] = build_context

    files_dest_path = Path(config.global_settings.routers_files_path / mac_fc)
    recreate_dir(files_dest_path)
    sfh = SharedFilesHandler(build_context)

    hrsf = RouterSpecificFilesHandler(build_context)
    sfh.handle_shared_files()
    hrsf.handle_router_specific_files()

    router_files.merge_files_to_router_files()

    return JSONResponse(
        content={
            "message": "Build prepared successfully.",
            "mac": mac,
            "ptah_version_hash": build_context.final_version,
            "download_url": f"/build/{mac}",
        },
        status_code=200,
    )


@router.post("/build/{mac}")
def download_build_endpoint(
    request: Request,
    mac: PortableMac,
    config: PtahConfig = Depends(get_config),
):
    ctx = cast(AppContext, request.app.state.ctx)
    if not ctx:
        raise HTTPException(
            status_code=500,
            detail="Application context not initialized.",
        )
    if mac not in ctx.build_contexts:
        return HTTPException(
            status_code=404,
            detail=f"Build context for {mac} not found. Please prepare the build first.",
        )
    build_context = ctx.build_contexts[mac]
    mac_fc = mac.to_filename_compliant()

    run_make_build(
        build_context.profile,
        config,
        mac_fc,
    )

    binary_name = build_context.profile.openwrt_profile.get_generated_binary_name(
        mac_fc
    )
    binary_path = config.global_settings.output_path / mac_fc / binary_name

    if not binary_path.exists():
        return HTTPException(
            status_code=500,
            detail=f"Build failed.",
        )

    if not binary_path.exists():
        raise HTTPException(
            status_code=404,
            detail="File not found",
        )
    download_binary_name = "ptah.bin"
    return FileResponse(
        path=binary_path,
        filename=download_binary_name,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={download_binary_name}",
        },
    )
