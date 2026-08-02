# @ai-generated
import os
import uuid
from typing import Optional, Tuple
import aiofiles

from src.config.env_config import EnvConfig
from src.common.cdn_url_util import CdnUrlUtil


class ObsUtil:
    _local_upload_base_dir: str = ""
    _local_static_prefix: str = ""
    _upload_temp_dir: str = ""

    @classmethod
    def initialize(cls) -> None:
        cls._local_upload_base_dir = EnvConfig.LOCAL_UPLOAD_BASE_DIR
        cls._local_static_prefix = EnvConfig.LOCAL_STATIC_PREFIX
        cls._upload_temp_dir = EnvConfig.UPLOAD_TEMP_DIR
        
        os.makedirs(cls._local_upload_base_dir, exist_ok=True)
        os.makedirs(cls._upload_temp_dir, exist_ok=True)

    @classmethod
    async def upload_file(cls, file_bytes: bytes, filename: str, prefix: str = "") -> Tuple[bool, str]:
        try:
            if not cls._local_upload_base_dir:
                cls.initialize()
            
            file_ext = cls._get_extension(filename)
            new_filename = f"{uuid.uuid4().hex}{file_ext}"
            upload_path = CdnUrlUtil.build_upload_path(prefix, new_filename)
            full_local_path = os.path.join(cls._local_upload_base_dir, upload_path)
            
            os.makedirs(os.path.dirname(full_local_path), exist_ok=True)
            
            async with aiofiles.open(full_local_path, "wb") as f:
                await f.write(file_bytes)
            
            static_url = f"{cls._local_static_prefix}/{upload_path}"
            cdn_url = CdnUrlUtil.get_cdn_url(upload_path)
            
            return True, cdn_url if cdn_url else static_url
        except Exception as e:
            return False, str(e)

    @classmethod
    async def upload_from_path(cls, local_path: str, prefix: str = "") -> Tuple[bool, str]:
        try:
            if not os.path.exists(local_path):
                return False, "File not found"
            
            filename = os.path.basename(local_path)
            
            async with aiofiles.open(local_path, "rb") as f:
                file_bytes = await f.read()
            
            return await cls.upload_file(file_bytes, filename, prefix)
        except Exception as e:
            return False, str(e)

    @classmethod
    async def delete_file(cls, path: str) -> Tuple[bool, str]:
        try:
            if not cls._local_upload_base_dir:
                cls.initialize()
            
            if path.startswith("http://") or path.startswith("https://"):
                path = CdnUrlUtil.remove_cdn_prefix(path)
            
            full_local_path = os.path.join(cls._local_upload_base_dir, path)
            
            if os.path.exists(full_local_path):
                os.remove(full_local_path)
                return True, "删除成功"
            
            return False, "文件不存在"
        except Exception as e:
            return False, str(e)

    @classmethod
    def get_upload_url(cls, path: str) -> str:
        return CdnUrlUtil.get_cdn_url(path)

    @classmethod
    def get_upload_path(cls, prefix: str, filename: str) -> str:
        return CdnUrlUtil.build_upload_path(prefix, filename)

    @classmethod
    def _get_extension(cls, filename: str) -> str:
        if "." in filename:
            return filename[filename.rfind("."):]
        return ""

    @classmethod
    async def save_temp_file(cls, file_bytes: bytes, filename: str) -> Tuple[bool, str]:
        try:
            if not cls._upload_temp_dir:
                cls.initialize()
            
            temp_path = os.path.join(cls._upload_temp_dir, filename)
            
            async with aiofiles.open(temp_path, "wb") as f:
                await f.write(file_bytes)
            
            return True, temp_path
        except Exception as e:
            return False, str(e)

    @classmethod
    async def clear_temp_file(cls, temp_path: str) -> bool:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                return True
            return False
        except Exception:
            return False