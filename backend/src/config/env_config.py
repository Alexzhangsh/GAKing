# @ai-generated
import os
import re
import sys
import logging
from decimal import Decimal, InvalidOperation
from typing import Optional, Any

from dotenv import load_dotenv

logger = logging.getLogger("env_config")

_PLACEHOLDER_PATTERN = re.compile(r"\{\{.*?\}\}")

_REQUIRED_COMMON_FIELDS = [
    "DB_HOST", "DB_USERNAME", "DB_PASSWORD", "DB_DATABASE",
    "REDIS_HOST",
    "JWT_SECRET",
    "OBS_ACCESS_KEY_ID", "OBS_SECRET_ACCESS_KEY", "OBS_BUCKET_NAME",
]

_CPS_FIELDS = [
    "MIAO_QUAN_TOKEN",
    "DATAOK_APPID", "DATAOK_APPKEY",
    "ORDERX_TOKEN",
]

_SENSITIVE_KEY_PATTERNS = [
    re.compile(r"(?i)(password|secret|token|key|api_key|app_key)"),
]


def _mask_sensitive(value: str) -> str:
    if not isinstance(value, str):
        return value
    for pattern in _SENSITIVE_KEY_PATTERNS:
        if pattern.search(value):
            return value[:2] + "***" + value[-2:] if len(value) > 4 else "***"
    return value


class EnvConfig:
    ENVIRONMENT: str = "development"
    PORT: int = 3001

    DB_HOST: str = ""
    DB_PORT: int = 3306
    DB_USERNAME: str = ""
    DB_PASSWORD: str = ""
    DB_DATABASE: str = ""
    TIMEZONE: str = "+08:00"

    REDIS_HOST: str = ""
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    JWT_SECRET: str = ""
    JWT_EXPIRES_IN: int = 3600

    CORS_ORIGINS: str = ""

    LOCAL_UPLOAD_BASE_DIR: str = "./static/uploads"
    LOCAL_STATIC_PREFIX: str = "/static/uploads"
    UPLOAD_TEMP_DIR: str = "./tmp"

    CDN_IMG_BASE_URL: str = ""
    OBS_PROJECT_PREFIX: str = "prod"
    OBS_ACCESS_KEY_ID: str = ""
    OBS_SECRET_ACCESS_KEY: str = ""
    OBS_ENDPOINT: str = "https://obs.cn-east-3.myhuaweicloud.com"
    OBS_BUCKET_NAME: str = ""

    MIAO_QUAN_TOKEN: str = ""
    DATAOK_APPID: str = ""
    DATAOK_APPKEY: str = ""
    ORDERX_TOKEN: str = ""

    RISK_HOLD_RATIO: float = 0.20
    SETTLE_COOL_DAY: int = 30
    SETTLE_DELAY_DAY: int = 7

    RATE_LIMIT_NORMAL: int = 60
    RATE_LIMIT_SEARCH: int = 20
    RATE_LIMIT_TRANSFORM: int = 100
    RATE_LIMIT_PAY: int = 10
    DATAOK_SEARCH_LIMIT: int = 100
    DATAOK_TRANSFORM_LIMIT: int = 300

    SCHEDULER_ENABLE: bool = True
    SHARD_TOTAL: int = 1
    SHARD_INDEX: int = 0

    SCHEDULER_CRON_SYNC_CONFIG: str = "0 * * * *"
    SCHEDULER_CRON_SYNC_ORDER_STATUS: str = "*/5 * * * *"
    SCHEDULER_CRON_CLEAN_EXPIRED_DATA: str = "0 3 * * *"
    SCHEDULER_CRON_UPDATE_CHANNEL_MAPPING: str = "0 2 * * *"
    SCHEDULER_RETRY_MAX: int = 3

    _loaded: bool = False

    @classmethod
    def load(cls) -> None:
        if cls._loaded:
            return
        env = os.getenv("ENVIRONMENT", "development")
        cls.ENVIRONMENT = env
        env_file = f".env.{env}"
        if os.path.exists(env_file):
            load_dotenv(env_file, override=False)
        elif os.path.exists(".env"):
            load_dotenv(".env", override=False)
        cls._loaded = True
        cls._load_values()

    @classmethod
    def _load_values(cls) -> None:
        cls.PORT = cls._get_int("PORT", 3001)

        cls.DB_HOST = cls._get_str("DB_HOST", "")
        cls.DB_PORT = cls._get_int("DB_PORT", 3306)
        cls.DB_USERNAME = cls._get_str("DB_USERNAME", "")
        cls.DB_PASSWORD = cls._get_str("DB_PASSWORD", "")
        cls.DB_DATABASE = cls._get_str("DB_DATABASE", "")
        cls.TIMEZONE = cls._get_str("TIMEZONE", "+08:00")

        cls.REDIS_HOST = cls._get_str("REDIS_HOST", "")
        cls.REDIS_PORT = cls._get_int("REDIS_PORT", 6379)
        cls.REDIS_DB = cls._get_int("REDIS_DB", 0)
        cls.REDIS_PASSWORD = cls._get_str("REDIS_PASSWORD", "") or None

        cls.JWT_SECRET = cls._get_str("JWT_SECRET", "")
        cls.JWT_EXPIRES_IN = cls._get_int("JWT_EXPIRES_IN", 3600)

        cls.CORS_ORIGINS = cls._get_str("CORS_ORIGINS", "")

        cls.LOCAL_UPLOAD_BASE_DIR = cls._get_str("LOCAL_UPLOAD_BASE_DIR", "./static/uploads")
        cls.LOCAL_STATIC_PREFIX = cls._get_str("LOCAL_STATIC_PREFIX", "/static/uploads")
        cls.UPLOAD_TEMP_DIR = cls._get_str("UPLOAD_TEMP_DIR", "./tmp")

        cls.CDN_IMG_BASE_URL = cls._get_str("CDN_IMG_BASE_URL", "")
        cls.OBS_PROJECT_PREFIX = cls._get_str("OBS_PROJECT_PREFIX", "prod")
        cls.OBS_ACCESS_KEY_ID = cls._get_str("OBS_ACCESS_KEY_ID", "")
        cls.OBS_SECRET_ACCESS_KEY = cls._get_str("OBS_SECRET_ACCESS_KEY", "")
        cls.OBS_ENDPOINT = cls._get_str("OBS_ENDPOINT", "https://obs.cn-east-3.myhuaweicloud.com")
        cls.OBS_BUCKET_NAME = cls._get_str("OBS_BUCKET_NAME", "")

        cls.MIAO_QUAN_TOKEN = cls._get_str("MIAO_QUAN_TOKEN", "")
        cls.DATAOK_APPID = cls._get_str("DATAOK_APPID", "")
        cls.DATAOK_APPKEY = cls._get_str("DATAOK_APPKEY", "")
        cls.ORDERX_TOKEN = cls._get_str("ORDERX_TOKEN", "")

        cls.RISK_HOLD_RATIO = cls._get_decimal("RISK_HOLD_RATIO", Decimal("0.20"))
        cls.SETTLE_COOL_DAY = cls._get_int("SETTLE_COOL_DAY", 30)
        cls.SETTLE_DELAY_DAY = cls._get_int("SETTLE_DELAY_DAY", 7)

        cls.RATE_LIMIT_NORMAL = cls._get_int("RATE_LIMIT_NORMAL", 60)
        cls.RATE_LIMIT_SEARCH = cls._get_int("RATE_LIMIT_SEARCH", 20)
        cls.RATE_LIMIT_TRANSFORM = cls._get_int("RATE_LIMIT_TRANSFORM", 100)
        cls.RATE_LIMIT_PAY = cls._get_int("RATE_LIMIT_PAY", 10)
        cls.DATAOK_SEARCH_LIMIT = cls._get_int("DATAOK_SEARCH_LIMIT", 100)
        cls.DATAOK_TRANSFORM_LIMIT = cls._get_int("DATAOK_TRANSFORM_LIMIT", 300)

        cls.SCHEDULER_ENABLE = cls._get_bool("SCHEDULER_ENABLE", True)
        cls.SHARD_TOTAL = cls._get_int("SHARD_TOTAL", 1)
        cls.SHARD_INDEX = cls._get_int("SHARD_INDEX", 0)

        cls.SCHEDULER_CRON_SYNC_CONFIG = cls._get_str("SCHEDULER_CRON_SYNC_CONFIG", "0 * * * *")
        cls.SCHEDULER_CRON_SYNC_ORDER_STATUS = cls._get_str("SCHEDULER_CRON_SYNC_ORDER_STATUS", "*/5 * * * *")
        cls.SCHEDULER_CRON_CLEAN_EXPIRED_DATA = cls._get_str("SCHEDULER_CRON_CLEAN_EXPIRED_DATA", "0 3 * * *")
        cls.SCHEDULER_CRON_UPDATE_CHANNEL_MAPPING = cls._get_str("SCHEDULER_CRON_UPDATE_CHANNEL_MAPPING", "0 2 * * *")
        cls.SCHEDULER_RETRY_MAX = cls._get_int("SCHEDULER_RETRY_MAX", 3)

    @classmethod
    def get_str(cls, key: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
        val = os.getenv(key, "")
        if _PLACEHOLDER_PATTERN.search(val):
            raise ValueError(f"Config key '{key}' contains unresolved placeholder: {val}")
        if not val:
            if required:
                raise ValueError(f"Required config key '{key}' is missing or empty")
            return default
        return val

    @classmethod
    def get_int(cls, key: str, default: Optional[int] = None, required: bool = False) -> Optional[int]:
        val = os.getenv(key, "")
        if _PLACEHOLDER_PATTERN.search(val):
            raise ValueError(f"Config key '{key}' contains unresolved placeholder: {val}")
        if not val:
            if required:
                raise ValueError(f"Required config key '{key}' is missing or empty")
            return default
        try:
            return int(val)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Config key '{key}' value '{_mask_sensitive(val)}' is not a valid integer") from e

    @classmethod
    def get_decimal(cls, key: str, default: Optional[Decimal] = None, required: bool = False) -> Optional[Decimal]:
        val = os.getenv(key, "")
        if _PLACEHOLDER_PATTERN.search(val):
            raise ValueError(f"Config key '{key}' contains unresolved placeholder: {val}")
        if not val:
            if required:
                raise ValueError(f"Required config key '{key}' is missing or empty")
            return default
        try:
            return Decimal(val)
        except (InvalidOperation, ValueError) as e:
            raise ValueError(f"Config key '{key}' value '{_mask_sensitive(val)}' is not a valid decimal") from e

    @classmethod
    def get_bool(cls, key: str, default: Optional[bool] = None, required: bool = False) -> Optional[bool]:
        val = os.getenv(key, "")
        if _PLACEHOLDER_PATTERN.search(val):
            raise ValueError(f"Config key '{key}' contains unresolved placeholder: {val}")
        if not val:
            if required:
                raise ValueError(f"Required config key '{key}' is missing or empty")
            return default
        return val.lower() in ("true", "1", "yes", "on")

    @classmethod
    def _get_str(cls, key: str, default: str = "") -> str:
        return os.getenv(key, default)

    @classmethod
    def _get_int(cls, key: str, default: int = 0) -> int:
        val = os.getenv(key, "")
        if not val:
            return default
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    @classmethod
    def _get_decimal(cls, key: str, default: Decimal = Decimal("0")) -> Decimal:
        val = os.getenv(key, "")
        if not val:
            return default
        try:
            return Decimal(val)
        except (InvalidOperation, ValueError):
            return default

    @classmethod
    def _get_bool(cls, key: str, default: bool = True) -> bool:
        val = os.getenv(key, "")
        if not val:
            return default
        return val.lower() in ("true", "1", "yes", "on")

    @classmethod
    def validate(cls) -> None:
        if not cls._loaded:
            cls.load()
        cls._check_placeholders()
        cls._validate_common()
        if cls.ENVIRONMENT == "production":
            cls._validate_production()

    @classmethod
    def _check_placeholders(cls) -> None:
        env_vars = {k: v for k, v in os.environ.items() if v and isinstance(v, str)}
        for key, value in env_vars.items():
            if _PLACEHOLDER_PATTERN.search(value):
                masked_val = _mask_sensitive(value)
                raise ValueError(
                    f"[{cls.ENVIRONMENT}] Config '{key}' contains unresolved placeholder: {masked_val}. "
                    f"Please replace all {{{{xxx}}}} placeholders before starting."
                )

    @classmethod
    def _validate_common(cls) -> None:
        missing = []
        for field in _REQUIRED_COMMON_FIELDS:
            val = getattr(cls, field, "")
            if not val:
                missing.append(field)

        if missing:
            raise ValueError(
                f"[{cls.ENVIRONMENT}] Missing required config: {', '.join(missing)}. "
                f"Please set these in .env.{cls.ENVIRONMENT} before starting."
            )

        if cls.DB_PASSWORD and _PLACEHOLDER_PATTERN.search(cls.DB_PASSWORD):
            raise ValueError("DB_PASSWORD contains unresolved placeholder")
        if cls.JWT_SECRET and len(cls.JWT_SECRET) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        if cls.RISK_HOLD_RATIO <= 0:
            raise ValueError("RISK_HOLD_RATIO must be greater than 0")
        if cls.SETTLE_COOL_DAY <= 0:
            raise ValueError("SETTLE_COOL_DAY must be greater than 0")
        if cls.SETTLE_DELAY_DAY <= 0:
            raise ValueError("SETTLE_DELAY_DAY must be greater than 0")

    @classmethod
    def _validate_production(cls) -> None:
        if cls.CORS_ORIGINS == "*":
            raise ValueError("Production CORS_ORIGINS cannot be '*'")
        if len(cls.JWT_SECRET) < 64:
            raise ValueError("Production JWT_SECRET must be at least 64 characters")
        cps_missing = [f for f in _CPS_FIELDS if not getattr(cls, f, "")]
        if cps_missing:
            raise ValueError(f"Production missing CPS tokens: {', '.join(cps_missing)}")

    @classmethod
    def is_production(cls) -> bool:
        return cls.ENVIRONMENT == "production"

    @classmethod
    def is_development(cls) -> bool:
        return cls.ENVIRONMENT == "development"

    @classmethod
    def get_db_url(cls) -> str:
        return (
            f"mysql+aiomysql://{cls.DB_USERNAME}:{cls.DB_PASSWORD}"
            f"@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_DATABASE}?charset=utf8mb4"
        )

    @classmethod
    def get_db_url_safe(cls) -> str:
        if cls.DB_PASSWORD:
            pwd = cls.DB_PASSWORD
            if len(pwd) > 4:
                safe_pwd = pwd[:2] + "***" + pwd[-2:]
            else:
                safe_pwd = "***"
        else:
            safe_pwd = ""
        return (
            f"mysql+aiomysql://{cls.DB_USERNAME}:{safe_pwd}"
            f"@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_DATABASE}"
        )


EnvConfig.load()
