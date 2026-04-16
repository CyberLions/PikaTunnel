import asyncio
import logging
import os
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ProxyRoute, StreamRoute, TLSCertificate
from app.config import settings

logger = logging.getLogger(__name__)

TLS_DIR = Path("/var/run/pikatunnel/tls")

# Match vpn_manager: in dev containers we run as vscode and the /var/run
# parent isn't ours, so fall back to `sudo -n` for privileged filesystem ops.
_SUDO: list[str] = [] if os.geteuid() == 0 else ["sudo", "-n"]


async def _run_priv(*args: str) -> tuple[int, str, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *_SUDO, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode(errors="ignore"), stderr.decode(errors="ignore")
    except FileNotFoundError:
        return 1, "", f"{args[0]} not found"


async def _ensure_tls_dir() -> None:
    """Create TLS_DIR, escalating to `sudo -n mkdir/chown` when the parent
    (e.g. /var/run in a dev container or a container running as non-root)
    isn't writable by the current user."""
    if TLS_DIR.exists() and os.access(TLS_DIR, os.W_OK):
        return
    try:
        TLS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(TLS_DIR, 0o700)
        except OSError:
            pass
        return
    except PermissionError:
        pass
    rc, _, err = await _run_priv("mkdir", "-p", str(TLS_DIR))
    if rc != 0:
        logger.error("Failed to mkdir %s: %s", TLS_DIR, err.strip())
        raise PermissionError(f"cannot create {TLS_DIR}: {err.strip()}")
    # Make the parent pikatunnel dir owned by us so future mkdirs don't need sudo.
    await _run_priv("chown", "-R", f"{os.getuid()}:{os.getgid()}", str(TLS_DIR.parent))
    await _run_priv("chmod", "700", str(TLS_DIR))


async def _materialize_certs(db: AsyncSession) -> dict[str, tuple[str, str]]:
    """Return mapping name -> (cert_path, key_path).

    For certs backed by mounted files (cert_path/key_path set), we use those
    paths directly so rotation happens naturally when the underlying k8s
    Secret updates. For inline certs, PEM bodies get written under TLS_DIR.
    """
    await _ensure_tls_dir()

    result = await db.execute(select(TLSCertificate))
    certs = result.scalars().all()
    mapping: dict[str, tuple[str, str]] = {}
    for c in certs:
        if c.cert_path and c.key_path:
            mapping[c.name] = (c.cert_path, c.key_path)
            continue
        if not (c.cert_pem and c.key_pem):
            logger.warning("TLS cert '%s' has no usable source; skipping", c.name)
            continue
        crt = TLS_DIR / f"{c.name}.crt"
        key = TLS_DIR / f"{c.name}.key"
        crt.write_text(c.cert_pem)
        key.write_text(c.key_pem)
        try:
            os.chmod(crt, 0o644)
            os.chmod(key, 0o600)
        except OSError:
            pass
        mapping[c.name] = (str(crt), str(key))
    return mapping


def _resolve_cert_paths(route: ProxyRoute, cert_map: dict[str, tuple[str, str]]) -> tuple[str, str] | None:
    """Return (cert_path, key_path) for this route if it can do TLS, else None."""
    if not route.ssl_enabled:
        return None
    if route.ssl_cert_name and route.ssl_cert_name in cert_map:
        return cert_map[route.ssl_cert_name]
    if route.ssl_cert_path and route.ssl_key_path:
        return (route.ssl_cert_path, route.ssl_key_path)
    return None


def _generate_http_config(routes: list[ProxyRoute], cert_map: dict[str, tuple[str, str]]) -> str:
    server_blocks: dict[str, dict] = {}

    for route in routes:
        if route.host not in server_blocks:
            server_blocks[route.host] = {"locations": [], "ssl": None}
        server_blocks[route.host]["locations"].append(route)
        resolved = _resolve_cert_paths(route, cert_map)
        if resolved and server_blocks[route.host]["ssl"] is None:
            server_blocks[route.host]["ssl"] = resolved

    default_server = """    server {
        listen 80 default_server;
        listen 443 ssl default_server;
        server_name _;
        ssl_certificate /etc/nginx/ssl/default.crt;
        ssl_certificate_key /etc/nginx/ssl/default.key;
        return 444;
    }"""

    dynamic_blocks = []
    for host, data in server_blocks.items():
        ssl_lines = ""
        if data["ssl"]:
            cert_path, key_path = data["ssl"]
            ssl_lines = f"""
        listen 443 ssl;
        ssl_certificate {cert_path};
        ssl_certificate_key {key_path};"""

        location_blocks = []
        for route in data["locations"]:
            location_blocks.append(f"""        location {route.path} {{
            proxy_pass http://{route.destination}:{route.port};
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }}""")

        locations_str = "\n".join(location_blocks)
        dynamic_blocks.append(f"""    server {{
        listen 80;
        server_name {host};{ssl_lines}

{locations_str}
    }}""")

    dynamic_str = "\n\n".join(dynamic_blocks)

    return f"""load_module /usr/lib/nginx/modules/ngx_stream_module.so;

worker_processes auto;
events {{
    worker_connections 1024;
}}

include {settings.NGINX_STREAM_CONFIG_PATH};

http {{
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    sendfile        on;
    keepalive_timeout  65;

{default_server}

{dynamic_str}
}}
"""


def _generate_stream_config(routes: list[StreamRoute]) -> str:
    if not routes:
        return ""

    server_blocks = []
    for route in routes:
        udp_flag = " udp" if route.protocol.value == "udp" else ""
        pp = "on" if route.proxy_protocol else "off"
        server_blocks.append(f"""    server {{
        listen {route.listen_port}{udp_flag};
        proxy_pass {route.destination}:{route.port};
        proxy_protocol {pp};
    }}""")

    servers_str = "\n".join(server_blocks)
    return f"""stream {{
{servers_str}
}}
"""


async def generate_and_write(db: AsyncSession) -> tuple[str, str]:
    proxy_result = await db.execute(select(ProxyRoute).where(ProxyRoute.enabled == True))
    proxy_routes = list(proxy_result.scalars().all())

    stream_result = await db.execute(select(StreamRoute).where(StreamRoute.enabled == True))
    stream_routes = list(stream_result.scalars().all())

    cert_map = await _materialize_certs(db)

    http_config = _generate_http_config(proxy_routes, cert_map)
    stream_config = _generate_stream_config(stream_routes)

    try:
        Path(settings.NGINX_CONFIG_PATH).write_text(http_config)
        Path(settings.NGINX_STREAM_CONFIG_PATH).write_text(stream_config)
        logger.info("Wrote nginx configs to disk")
    except OSError as e:
        logger.warning("Failed to write nginx configs: %s", e)

    return http_config, stream_config


async def reload_nginx() -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            "nginx", "-s", "reload",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error("nginx reload failed: %s", stderr.decode())
            return False
        logger.info("nginx reloaded successfully")
        return True
    except FileNotFoundError:
        logger.warning("nginx binary not found — skipping reload")
        return False


async def generate_and_reload(db: AsyncSession) -> tuple[str, str]:
    configs = await generate_and_write(db)
    await reload_nginx()
    return configs


async def get_nginx_status() -> dict:
    try:
        proc = await asyncio.create_subprocess_exec(
            "nginx", "-t",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()
        config_ok = proc.returncode == 0
        config_error = None if config_ok else stderr.decode(errors="ignore").strip()
    except FileNotFoundError:
        return {"running": False, "pid": None, "config_valid": False, "config_error": "nginx binary not found"}

    try:
        pid_text = Path("/run/nginx.pid").read_text().strip()
        pid = int(pid_text)
        return {"running": True, "pid": pid, "config_valid": config_ok, "config_error": config_error}
    except (FileNotFoundError, ValueError):
        return {"running": False, "pid": None, "config_valid": config_ok, "config_error": config_error}
