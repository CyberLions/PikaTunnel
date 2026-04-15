import asyncio
import logging
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ProxyRoute, StreamRoute
from app.config import settings

logger = logging.getLogger(__name__)


def _generate_http_config(routes: list[ProxyRoute]) -> str:
    server_blocks: dict[str, dict] = {}

    for route in routes:
        if route.host not in server_blocks:
            server_blocks[route.host] = {"locations": [], "ssl": None}
        server_blocks[route.host]["locations"].append(route)
        if route.ssl_enabled and route.ssl_cert_path and route.ssl_key_path:
            server_blocks[route.host]["ssl"] = route

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
            r = data["ssl"]
            ssl_lines = f"""
        listen 443 ssl;
        ssl_certificate {r.ssl_cert_path};
        ssl_certificate_key {r.ssl_key_path};"""

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

    http_config = _generate_http_config(proxy_routes)
    stream_config = _generate_stream_config(stream_routes)

    try:
        proc = await asyncio.create_subprocess_shell(
            f"sudo tee {settings.NGINX_CONFIG_PATH} > /dev/null",
            stdin=asyncio.subprocess.PIPE,
        )
        await proc.communicate(input=http_config.encode())
        proc = await asyncio.create_subprocess_shell(
            f"sudo tee {settings.NGINX_STREAM_CONFIG_PATH} > /dev/null",
            stdin=asyncio.subprocess.PIPE,
        )
        await proc.communicate(input=stream_config.encode())
        logger.info("Wrote nginx configs to disk")
    except OSError as e:
        logger.warning("Failed to write nginx configs: %s", e)

    return http_config, stream_config


async def reload_nginx() -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            "sudo", "nginx", "-s", "reload",
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
            "sudo", "nginx", "-t",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        config_ok = proc.returncode == 0
    except FileNotFoundError:
        return {"running": False, "pid": None}

    try:
        pid_text = Path("/run/nginx.pid").read_text().strip()
        pid = int(pid_text)
        return {"running": True, "pid": pid, "config_valid": config_ok}
    except (FileNotFoundError, ValueError):
        return {"running": False, "pid": None, "config_valid": config_ok}
