import abc
import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import VPNConfig

logger = logging.getLogger(__name__)


class VPNProvider(abc.ABC):
    @abc.abstractmethod
    async def connect(self, config: VPNConfig) -> str:
        ...

    @abc.abstractmethod
    async def disconnect(self, config: VPNConfig) -> str:
        ...

    @abc.abstractmethod
    async def status(self, config: VPNConfig) -> str:
        ...


class PritunlProvider(VPNProvider):
    async def _run(self, *args: str) -> tuple[int, str, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return proc.returncode, stdout.decode(), stderr.decode()
        except FileNotFoundError:
            logger.error("pritunl-client binary not found")
            return 1, "", "pritunl-client not found"

    async def connect(self, config: VPNConfig) -> str:
        profile_path = config.config_data.get("profile_path", "")
        if not profile_path:
            return "error"

        rc, out, err = await self._run("pritunl-client", "add", profile_path)
        if rc != 0:
            logger.error("Failed to add profile: %s", err)
            return "error"

        rc, out, err = await self._run("pritunl-client", "list")
        if rc != 0:
            return "error"

        profile_id = None
        for line in out.splitlines():
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if parts and len(parts[0]) >= 14 and parts[0].isalnum():
                profile_id = parts[0]
                break

        if not profile_id:
            return "error"

        rc, out, err = await self._run("pritunl-client", "start", profile_id)
        if rc != 0:
            logger.error("Failed to start connection: %s", err)
            return "error"

        for _ in range(12):
            await asyncio.sleep(5)
            current = await self.status(config)
            if current == "connected":
                return "connected"

        return "error"

    async def disconnect(self, config: VPNConfig) -> str:
        rc, out, err = await self._run("pritunl-client", "list")
        if rc != 0:
            return "error"

        profile_id = None
        for line in out.splitlines():
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if parts and len(parts[0]) >= 14 and parts[0].isalnum():
                profile_id = parts[0]
                break

        if profile_id:
            await self._run("pritunl-client", "stop", profile_id)
            await self._run("pritunl-client", "remove", profile_id)

        return "disconnected"

    async def status(self, config: VPNConfig) -> str:
        rc, out, err = await self._run("pritunl-client", "list")
        if rc != 0:
            return "error"
        if "Active" in out:
            return "connected"
        return "disconnected"


_providers: dict[str, VPNProvider] = {
    "pritunl": PritunlProvider(),
}


def get_provider(vpn_type: str) -> VPNProvider:
    provider = _providers.get(vpn_type)
    if not provider:
        raise ValueError(f"Unsupported VPN type: {vpn_type}")
    return provider


async def connect(config: VPNConfig, db: AsyncSession) -> str:
    provider = get_provider(config.vpn_type)
    config.status = "connecting"
    db.add(config)
    await db.commit()

    status = await provider.connect(config)
    config.status = status
    db.add(config)
    await db.commit()
    return status


async def disconnect(config: VPNConfig, db: AsyncSession) -> str:
    provider = get_provider(config.vpn_type)
    status = await provider.disconnect(config)
    config.status = status
    db.add(config)
    await db.commit()
    return status


async def get_status(config: VPNConfig) -> str:
    provider = get_provider(config.vpn_type)
    return await provider.status(config)
