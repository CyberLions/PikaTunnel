import asyncio
import logging
import os
import signal
import time
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import VPNConfig

logger = logging.getLogger(__name__)

RUN_DIR = Path("/var/run/pikatunnel")
OVPN_CONF = RUN_DIR / "openvpn.conf"
OVPN_PID = RUN_DIR / "openvpn.pid"
OVPN_LOG = RUN_DIR / "openvpn.log"

WG_IFACE = "pika0"
WG_CONF = Path(f"/etc/wireguard/{WG_IFACE}.conf")

# WG is considered connected if a handshake happened within this many seconds.
WG_HANDSHAKE_FRESH_SECS = 180


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


def _detect_protocol(config_data: dict) -> tuple[str, str] | None:
    """Return (protocol, config_text) or None if nothing usable is present."""
    wg = config_data.get("wg_config")
    ovpn = config_data.get("ovpn_config")
    if wg:
        return "wireguard", wg
    if ovpn:
        return "openvpn", ovpn
    return None


# ---- OpenVPN ----------------------------------------------------------------

def _ovpn_read_pid() -> int | None:
    try:
        return int(OVPN_PID.read_text().strip())
    except (OSError, ValueError):
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


async def _ovpn_stop() -> None:
    pid = _ovpn_read_pid()
    if pid and _pid_alive(pid):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        for _ in range(20):
            await asyncio.sleep(0.5)
            if not _pid_alive(pid):
                break
        else:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    for p in (OVPN_PID, OVPN_LOG, OVPN_CONF):
        try:
            p.unlink()
        except OSError:
            pass


async def _ovpn_start(ovpn_text: str) -> bool:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    OVPN_CONF.write_text(ovpn_text)
    rc, _, err = await _run(
        "openvpn",
        "--config", str(OVPN_CONF),
        "--daemon",
        "--writepid", str(OVPN_PID),
        "--log", str(OVPN_LOG),
    )
    if rc != 0:
        logger.error("openvpn failed to start: %s", err)
        return False
    # Give the daemon a beat to write the pidfile.
    for _ in range(10):
        if OVPN_PID.exists():
            return True
        await asyncio.sleep(0.2)
    return True


def _ovpn_status() -> str:
    pid = _ovpn_read_pid()
    if not pid or not _pid_alive(pid):
        return "disconnected"
    try:
        log = OVPN_LOG.read_text(errors="ignore")
    except OSError:
        return "connecting"
    if "Initialization Sequence Completed" in log:
        return "connected"
    return "connecting"


# ---- WireGuard --------------------------------------------------------------

async def _wg_iface_exists() -> bool:
    rc, _, _ = await _run("ip", "link", "show", WG_IFACE)
    return rc == 0


async def _wg_stop() -> None:
    if await _wg_iface_exists():
        await _run("wg-quick", "down", WG_IFACE)
    try:
        WG_CONF.unlink()
    except OSError:
        pass


async def _wg_start(wg_text: str) -> bool:
    WG_CONF.parent.mkdir(parents=True, exist_ok=True)
    WG_CONF.write_text(wg_text)
    os.chmod(WG_CONF, 0o600)
    rc, _, err = await _run("wg-quick", "up", WG_IFACE)
    if rc != 0:
        logger.error("wg-quick up failed: %s", err)
        return False
    return True


async def _wg_status() -> str:
    if not await _wg_iface_exists():
        return "disconnected"
    rc, out, _ = await _run("wg", "show", WG_IFACE, "latest-handshakes")
    if rc != 0:
        return "connecting"
    now = int(time.time())
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            try:
                ts = int(parts[1])
            except ValueError:
                continue
            if ts > 0 and now - ts < WG_HANDSHAKE_FRESH_SECS:
                return "connected"
    return "connecting"


# ---- Public API -------------------------------------------------------------

async def _stop_all() -> None:
    await _ovpn_stop()
    await _wg_stop()


async def connect(config: VPNConfig, db: AsyncSession) -> str:
    detected = _detect_protocol(config.config_data or {})
    if not detected:
        logger.error("No ovpn_config or wg_config in config_data for %s", config.name)
        config.status = "error"
        db.add(config)
        await db.commit()
        return "error"
    protocol, text = detected

    config.status = "connecting"
    db.add(config)
    await db.commit()

    await _stop_all()

    started = await (_ovpn_start(text) if protocol == "openvpn" else _wg_start(text))
    if not started:
        config.status = "error"
        db.add(config)
        await db.commit()
        return "error"

    for _ in range(12):
        await asyncio.sleep(5)
        status = await get_status(config)
        if status == "connected":
            config.status = "connected"
            db.add(config)
            await db.commit()
            return "connected"

    logger.error("Timed out waiting for %s connection on %s", protocol, config.name)
    await _stop_all()
    config.status = "error"
    db.add(config)
    await db.commit()
    return "error"


async def disconnect(config: VPNConfig, db: AsyncSession) -> str:
    await _stop_all()
    config.status = "disconnected"
    db.add(config)
    await db.commit()
    return "disconnected"


async def get_status(config: VPNConfig) -> str:
    detected = _detect_protocol(config.config_data or {})
    protocol = detected[0] if detected else None
    if protocol == "wireguard":
        return await _wg_status()
    if protocol == "openvpn":
        return _ovpn_status()
    # Fall back to whichever is actually running.
    if _ovpn_read_pid():
        return _ovpn_status()
    if await _wg_iface_exists():
        return await _wg_status()
    return "disconnected"
