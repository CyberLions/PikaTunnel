import asyncio
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import VPNConfig

logger = logging.getLogger(__name__)

# After a manual disconnect, pause the autoreconnect watcher for this long
# so the user isn't fighting it. An explicit Connect clears the suspension.
RECONNECT_SUSPEND_MINUTES = 10

RUN_DIR = Path("/var/run/pikatunnel")
OVPN_CONF = RUN_DIR / "openvpn.conf"
OVPN_PID = RUN_DIR / "openvpn.pid"
OVPN_LOG = RUN_DIR / "openvpn.log"

WG_IFACE = "pika0"
WG_CONF = RUN_DIR / f"{WG_IFACE}.conf"
WG_LOG = RUN_DIR / "wireguard.log"

WG_HANDSHAKE_FRESH_SECS = 180

# Prod container runs as root; dev container runs as vscode w/ passwordless sudo.
SUDO: list[str] = [] if os.geteuid() == 0 else ["sudo", "-n"]


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


async def _run_priv(*args: str) -> tuple[int, str, str]:
    return await _run(*SUDO, *args)


async def _ensure_run_dir() -> None:
    if RUN_DIR.exists() and os.access(RUN_DIR, os.W_OK):
        return
    try:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        return
    except PermissionError:
        pass
    await _run_priv("mkdir", "-p", str(RUN_DIR))
    await _run_priv("chown", f"{os.getuid()}:{os.getgid()}", str(RUN_DIR))


def _detect_protocol(config_data: dict) -> tuple[str, str] | None:
    wg = config_data.get("wg_config")
    ovpn = config_data.get("ovpn_config")
    if wg:
        return "wireguard", wg
    if ovpn:
        return "openvpn", ovpn
    return None


# ---- OpenVPN ----------------------------------------------------------------

def _pid_alive(pid: int) -> bool:
    return Path(f"/proc/{pid}").exists()


def _ovpn_read_pid() -> int | None:
    try:
        return int(OVPN_PID.read_text().strip())
    except (OSError, ValueError):
        return None


async def _ovpn_stop() -> None:
    pid = _ovpn_read_pid()
    if pid and _pid_alive(pid):
        await _run_priv("kill", "-TERM", str(pid))
        for _ in range(20):
            await asyncio.sleep(0.5)
            if not _pid_alive(pid):
                break
        else:
            await _run_priv("kill", "-KILL", str(pid))
    # Keep OVPN_LOG so failures remain inspectable via the logs UI; it is
    # truncated on the next start via openvpn's --log flag.
    for p in (OVPN_PID, OVPN_CONF):
        try:
            p.unlink()
        except OSError:
            pass


def _normalize_ovpn(text: str) -> str:
    """Fix common PEM-corruption patterns from UI round-trips.

    OpenSSL 3 strictly rejects inline certs with leading whitespace on PEM
    markers/base64 lines or non-ASCII spaces. Normalize: CRLF→LF, drop
    BOM/zero-width/no-break-spaces, and left-strip every line inside a
    -----BEGIN/END----- block.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\ufeff", "").replace("\u200b", "").replace("\u00a0", " ")
    out: list[str] = []
    in_pem = False
    for raw in text.split("\n"):
        line = raw.rstrip()
        stripped = line.lstrip()
        if stripped.startswith("-----BEGIN"):
            in_pem = True
            out.append(stripped)
        elif stripped.startswith("-----END"):
            in_pem = False
            out.append(stripped)
        elif in_pem:
            out.append(stripped)
        else:
            out.append(line)
    return "\n".join(out)


async def _ovpn_start(ovpn_text: str) -> bool:
    await _ensure_run_dir()
    OVPN_CONF.write_text(_normalize_ovpn(ovpn_text))
    rc, out, err = await _run_priv(
        "openvpn",
        "--config", str(OVPN_CONF),
        "--daemon",
        "--writepid", str(OVPN_PID),
        "--log", str(OVPN_LOG),
    )
    if rc != 0:
        logger.error("openvpn failed to start: %s", err)
        # If openvpn bailed before opening --log, persist what it told us
        # on stderr/stdout so the logs UI surfaces the reason.
        try:
            OVPN_LOG.write_text(
                f"[pikatunnel] openvpn init failed (rc={rc})\n"
                f"--- stderr ---\n{err}\n--- stdout ---\n{out}\n"
            )
        except OSError:
            pass
        return False
    for _ in range(10):
        if OVPN_PID.exists():
            break
        await asyncio.sleep(0.2)
    return True


async def _ovpn_running() -> bool:
    pid = _ovpn_read_pid()
    if pid and _pid_alive(pid):
        return True
    # Pidfile might not have been written yet, or got stripped on a crash
    # restart where the daemon survived. pgrep is the ground truth inside
    # this container's PID namespace.
    rc, _, _ = await _run("pgrep", "-x", "openvpn")
    return rc == 0


async def _ovpn_read_log() -> str:
    try:
        return OVPN_LOG.read_text(errors="ignore")
    except OSError:
        pass
    rc, out, _ = await _run_priv("cat", str(OVPN_LOG))
    return out if rc == 0 else ""


async def _ovpn_status() -> str:
    if not await _ovpn_running():
        return "disconnected"
    if "Initialization Sequence Completed" in await _ovpn_read_log():
        return "connected"
    return "connecting"


# ---- WireGuard --------------------------------------------------------------

async def _wg_iface_exists() -> bool:
    rc, _, _ = await _run("ip", "link", "show", WG_IFACE)
    return rc == 0


def _append_wg_log(entry: str) -> None:
    try:
        with WG_LOG.open("a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {entry}\n")
    except OSError:
        pass


async def _wg_stop() -> None:
    if await _wg_iface_exists():
        rc, out, err = await _run_priv("wg-quick", "down", str(WG_CONF))
        _append_wg_log(f"$ wg-quick down (rc={rc})\n{out}{err}")
    # Config contains a private key — remove it. WG_LOG is retained.
    try:
        WG_CONF.unlink()
    except OSError:
        pass


async def _wg_start(wg_text: str) -> bool:
    await _ensure_run_dir()
    # Fresh log per connection attempt.
    try:
        WG_LOG.unlink()
    except OSError:
        pass
    # Strip DNS — wg-quick shells out to resolvconf, which isn't installed
    # and we don't want the tunnel mutating the pod's /etc/resolv.conf anyway.
    wg_text = "\n".join(
        l for l in wg_text.splitlines() if not l.strip().lower().startswith("dns")
    )
    WG_CONF.write_text(wg_text)
    os.chmod(WG_CONF, 0o600)
    rc, out, err = await _run_priv("wg-quick", "up", str(WG_CONF))
    _append_wg_log(f"$ wg-quick up (rc={rc})\n{out}{err}")
    if rc != 0:
        logger.error("wg-quick up failed: %s", err)
        return False
    return True


async def _wg_status() -> str:
    if not await _wg_iface_exists():
        return "disconnected"
    rc, out, _ = await _run_priv("wg", "show", WG_IFACE, "latest-handshakes")
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
    """Kick off the VPN daemon and return immediately.

    The UI converges on the real state via refresh_status() on subsequent
    list/status polls — we don't block the HTTP request for up to 60s.
    """
    detected = _detect_protocol(config.config_data or {})
    if not detected:
        logger.error("No ovpn_config or wg_config in config_data for %s", config.name)
        config.status = "error"
        db.add(config)
        await db.commit()
        return "error"
    protocol, text = detected

    await _stop_all()

    started = await (_ovpn_start(text) if protocol == "openvpn" else _wg_start(text))
    if not started:
        config.status = "error"
        db.add(config)
        await db.commit()
        return "error"

    config.status = "connecting"
    # Explicit Connect clears any disconnect-induced suspension so the
    # autoreconnect watcher takes over again if the tunnel later drops.
    config.reconnect_suspended_until = None
    db.add(config)
    await db.commit()
    return "connecting"


async def refresh_status(config: VPNConfig, db: AsyncSession) -> str:
    """Reconcile the stored status with the live daemon state and persist."""
    live = await get_status(config)
    if config.status != live:
        config.status = live
        db.add(config)
        await db.commit()
    return live


async def disconnect(config: VPNConfig, db: AsyncSession) -> str:
    await _stop_all()
    config.status = "disconnected"
    # Suspend the autoreconnect watcher so this manual disconnect isn't
    # immediately undone. Explicit Connect (or editing the config) clears it;
    # otherwise it expires automatically after RECONNECT_SUSPEND_MINUTES.
    config.reconnect_suspended_until = datetime.now(timezone.utc) + timedelta(minutes=RECONNECT_SUSPEND_MINUTES)
    db.add(config)
    await db.commit()
    return "disconnected"


async def get_logs(config: VPNConfig, tail_lines: int = 500) -> str:
    detected = _detect_protocol(config.config_data or {})
    protocol = detected[0] if detected else None

    if protocol == "openvpn" or (protocol is None and await _ovpn_running()):
        rc, out, err = await _run_priv("cat", str(OVPN_LOG))
        if rc != 0:
            return f"(no openvpn log available: {err.strip() or 'not started yet'})"
        lines = out.splitlines()
        if len(lines) > tail_lines:
            lines = lines[-tail_lines:]
        return "\n".join(lines)

    if protocol == "wireguard" or await _wg_iface_exists() or WG_LOG.exists():
        sections: list[str] = []
        try:
            sections.append(f"--- {WG_LOG.name} ---\n{WG_LOG.read_text(errors='ignore')}")
        except OSError:
            sections.append("(no wg-quick log yet)")
        rc, out, _ = await _run_priv("wg", "show", WG_IFACE)
        sections.append(f"$ wg show {WG_IFACE}\n{out if rc == 0 else '(interface not up)'}")
        rc, out, _ = await _run("ip", "addr", "show", WG_IFACE)
        sections.append(f"$ ip addr show {WG_IFACE}\n{out if rc == 0 else '(interface not found)'}")
        return "\n\n".join(sections)

    return "(no active VPN session; connect first to generate logs)"


async def get_status(config: VPNConfig) -> str:
    detected = _detect_protocol(config.config_data or {})
    protocol = detected[0] if detected else None
    if protocol == "wireguard":
        return await _wg_status()
    if protocol == "openvpn":
        return await _ovpn_status()
    if await _ovpn_running():
        return await _ovpn_status()
    if await _wg_iface_exists():
        return await _wg_status()
    return "disconnected"
