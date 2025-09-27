from pathlib import Path
import subprocess
from typing import Annotated, cast
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from ptah.models.build import BuildPrepareRequest
from ptah.models import PtahConfig, PtahProfile
from ptah.contexts import BuildContext, AppContext
from ptah.models import RouterFilesOrganizer
from ptah.models import PortableMac
from ptah.models import Versions
from ptah.utils.handle_router_specific_files import RouterSpecificFilesHandler
from ptah.utils.handle_shared_files import SharedFilesHandler
from ptah.utils.utils import recreate_dir
from ptah.api.dependencies import check_mac_matches_payload, get_config, read_secrets
from ptah.env import ENV

if ENV.deploy_env in ("local"):
    router = APIRouter(prefix="/build", tags=["Build"])
else:
    router = APIRouter(
        prefix="/build",
        tags=["Build"],
        dependencies=[Depends(check_mac_matches_payload)],
    )


def check_profile_exists(profile: str, config: PtahConfig) -> PtahProfile:
    for ptah_profile in config.ptah_profiles:
        if ptah_profile.name == profile:
            return ptah_profile
    return None


def run_make_build(profile: PtahProfile, mac: str) -> bool:
    packages = " ".join(profile.packages) if profile.packages else ""
    make_image_cmd = [
        "make",
        "image",
        f"PROFILE={profile.openwrt_profile.name}",
        f"PACKAGES={packages}",
        f"EXTRA_IMAGE_NAME=ptah-{mac}",
        f"BIN_DIR={ENV.output_path / mac}",
        f"FILES={ENV.routers_files_path / mac}",
    ]

    profile_path = ENV.builders_path / profile.name
    with open(profile_path / "builder_folder", encoding="utf-8") as f:
        builder_name = f.readline().strip("\n")
    builder_path = profile_path / builder_name

    recreate_dir(ENV.output_path / mac)

    try:
        subprocess.run(make_image_cmd, check=True, cwd=builder_path)
    except subprocess.CalledProcessError as exc:
        raise HTTPException(
            status_code=500,
            detail="Build failed.",
        ) from exc

    return True


@router.post("/prepare/{mac}")
def build_endpoint(
    request: Request,
    mac: PortableMac,
    request_data: BuildPrepareRequest,
    config: Annotated[PtahConfig, Depends(get_config)],
    secrets: Annotated[dict, Depends(read_secrets)],
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
    )

    build_context = BuildContext(
        mac=mac,
        profile=ptah_profile,
        secrets=secrets,
        versions=Versions(ptah_profile),
        router_files=router_files,
    )
    build_contexts[mac] = build_context

    files_dest_path = Path(ENV.routers_files_path / mac_fc)
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


@router.post("/{mac}")
def download_build_endpoint(
    request: Request,
    mac: PortableMac,
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
        mac_fc,
    )

    binary_name = build_context.profile.openwrt_profile.get_generated_binary_name(
        mac_fc
    )
    binary_path = ENV.output_path / mac_fc / binary_name

    if not binary_path.exists():
        return HTTPException(
            status_code=500,
            detail="Build failed.",
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
