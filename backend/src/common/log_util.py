# @ai-generated
import logging
import os
import re
from typing import Dict, Any
from logging.handlers import RotatingFileHandler

from src.config.env_config import EnvConfig


class SensitiveDataMasker:
    _patterns = {
        "phone": r"(\d{3})\d{4}(\d{4})",
        "email": r"([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
        "id_card": r"(\d{4})\d{10}(\d{4})",
        "bank_card": r"(\d{4})\d{8,12}(\d{4})",
        "password": r"\"password\"[^\"]*\"([^\"]*)\"",
        "secret": r"\"secret\"[^\"]*\"([^\"]*)\"",
        "token": r"\"token\"[^\"]*\"([^\"]*)\"",
        "api_key": r"\"api_key\"[^\"]*\"([^\"]*)\"",
    }

    _replacements = {
        "phone": r"\1****\2",
        "email": r"\1***@\2",
        "id_card": r"\1**********\2",
        "bank_card": r"\1********\2",
        "password": r'"password": "***"',
        "secret": r'"secret": "***"',
        "token": r'"token": "***"',
        "api_key": r'"api_key": "***"',
    }

    @classmethod
    def mask(cls, data: str) -> str:
        if not isinstance(data, str):
            return str(data)
        
        result = data
        for pattern_name, pattern in cls._patterns.items():
            result = re.sub(pattern, cls._replacements[pattern_name], result)
        
        return result

    @classmethod
    def mask_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = cls.mask(value)
            elif isinstance(value, dict):
                result[key] = cls.mask_dict(value)
            elif isinstance(value, list):
                result[key] = [cls.mask_dict(item) if isinstance(item, dict) else cls.mask(str(item)) for item in value]
            else:
                result[key] = value
        
        return result


class LogConfig:
    _log_dir = "./logs"
    _max_bytes = 10 * 1024 * 1024
    _backup_count = 10

    @classmethod
    def initialize(cls) -> None:
        os.makedirs(cls._log_dir, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO if EnvConfig.is_production() else logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                RotatingFileHandler(
                    os.path.join(cls._log_dir, "app.log"),
                    maxBytes=cls._max_bytes,
                    backupCount=cls._backup_count,
                    encoding="utf-8",
                ),
                logging.StreamHandler(),
            ],
        )

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO if EnvConfig.is_production() else logging.DEBUG)
        return logger

    @classmethod
    def safe_log(cls, logger: logging.Logger, level: str, message: str, **kwargs) -> None:
        masked_message = SensitiveDataMasker.mask(message)
        masked_kwargs = SensitiveDataMasker.mask_dict(kwargs)
        
        log_method = getattr(logger, level.lower(), logger.info)
        
        if masked_kwargs:
            log_method(masked_message, masked_kwargs)
        else:
            log_method(masked_message)

    @classmethod
    def log_request(cls, logger: logging.Logger, method: str, url: str, params: dict = None, body: dict = None):
        masked_params = SensitiveDataMasker.mask_dict(params) if params else None
        masked_body = SensitiveDataMasker.mask_dict(body) if body else None
        
        logger.info(
            f"Request: {method} {url}",
            extra={
                "params": masked_params,
                "body": masked_body,
            },
        )

    @classmethod
    def log_response(cls, logger: logging.Logger, status_code: int, response: dict = None):
        masked_response = SensitiveDataMasker.mask_dict(response) if response else None
        
        logger.info(
            f"Response: {status_code}",
            extra={
                "response": masked_response,
            },
        )

    @classmethod
    def log_error(cls, logger: logging.Logger, error: Exception, context: dict = None):
        masked_context = SensitiveDataMasker.mask_dict(context) if context else None
        
        logger.error(
            f"Error: {str(error)}",
            exc_info=True,
            extra={
                "context": masked_context,
            },
        )