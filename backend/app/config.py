import secrets
import logging
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://proxy_manager:proxy_manager@db:5432/proxy_manager"
    SECRET_KEY: str = ""
    ENVIRONMENT: str = "development"
    VPN_ENABLED: bool = False
    VPN_TYPE: str = "pritunl"
    NGINX_CONFIG_PATH: str = "/etc/nginx/nginx.conf"
    NGINX_STREAM_CONFIG_PATH: str = "/etc/nginx/nginx.stream.conf"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    model_config = {"env_prefix": "", "case_sensitive": True}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.SECRET_KEY:
            self.SECRET_KEY = secrets.token_urlsafe(32)
            logger.warning("No SECRET_KEY set — generated a random key. Set SECRET_KEY env var for production.")


settings = Settings()
