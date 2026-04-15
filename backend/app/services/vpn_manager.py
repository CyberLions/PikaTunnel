import asyncio
import logging
import tarfile
import tempfile
import io
import os
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import VPNConfig

logger = logging.getLogger(__name__)


async def _run(*args: str) -> tuple[int, str, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode(), stderr.decode()
    except FileNotFoundError:
        logger.error("binary not found: %s", args[0])
        return 1, "", f"{args[0]} not found"


def _build_tar(name: str, ovpn_config: str) -> str:
    """Build a .tar containing the .ovpn file, return the temp path."""
    ovpn_bytes = ovpn_config.encode()
    tmp = tempfile.NamedTemporaryFile(suffix=".tar", prefix=f"pika-{name}-", delete=False)
    with tarfile.open(tmp.name, "w") as tar:
        info = tarfile.TarInfo(name=f"{name}.ovpn")
        info.size = len(ovpn_bytes)
        tar.addfile(info, io.BytesIO(ovpn_bytes))
    return tmp.name


def _parse_profile_id(output: str) -> str | None:
    """Parse the profile ID from `pritunl-client list` output."""
    for line in output.splitlines():
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if parts and len(parts[0]) >= 10 and parts[0].replace("-", "").isalnum():
            return parts[0]
    return None


async def _get_profile_id() -> str | None:
    rc, out, _ = await _run("pritunl-client", "list")
    if rc != 0:
        return None
    return _parse_profile_id(out)


async def connect(config: VPNConfig, db: AsyncSession) -> str:
    ovpn_config = config.config_data.get("ovpn_config", "")
    if not ovpn_config:
        logger.error("No ovpn_config in config_data for %s", config.name)
        config.status = "error"
        db.add(config)
        await db.commit()
        return "error"

    config.status = "connecting"
    db.add(config)
    await db.commit()

    # Remove any existing profile first
    existing = await _get_profile_id()
    if existing:
        await _run("pritunl-client", "stop", existing)
        await asyncio.sleep(1)
        await _run("pritunl-client", "remove", existing)

    # Build tar from DB config and add it
    tar_path = _build_tar(config.name, ovpn_config)
    try:
        rc, out, err = await _run("pritunl-client", "add", tar_path)
        if rc != 0:
            logger.error("Failed to add profile for %s: %s", config.name, err)
            config.status = "error"
            db.add(config)
            await db.commit()
            return "error"
    finally:
        os.unlink(tar_path)

    # Get profile ID and start
    profile_id = await _get_profile_id()
    if not profile_id:
        logger.error("Could not find profile after adding for %s", config.name)
        config.status = "error"
        db.add(config)
        await db.commit()
        return "error"

    rc, out, err = await _run("pritunl-client", "start", profile_id)
    if rc != 0:
        logger.error("Failed to start profile for %s: %s", config.name, err)
        config.status = "error"
        db.add(config)
        await db.commit()
        return "error"

    # Poll for connection
    for _ in range(12):
        await asyncio.sleep(5)
        status = await get_status(config)
        if status == "connected":
            config.status = "connected"
            db.add(config)
            await db.commit()
            return "connected"

    logger.error("Timed out waiting for connection on %s", config.name)
    config.status = "error"
    db.add(config)
    await db.commit()
    return "error"


async def disconnect(config: VPNConfig, db: AsyncSession) -> str:
    profile_id = await _get_profile_id()
    if profile_id:
        await _run("pritunl-client", "stop", profile_id)
        await asyncio.sleep(1)
        await _run("pritunl-client", "remove", profile_id)

    config.status = "disconnected"
    db.add(config)
    await db.commit()
    return "disconnected"


async def get_status(config: VPNConfig) -> str:
    rc, out, _ = await _run("pritunl-client", "list")
    if rc != 0:
        return "error"
    lower = out.lower()
    if "connected" in lower:
        return "connected"
    if "connecting" in lower or "reconnecting" in lower:
        return "connecting"
    return "disconnected"
