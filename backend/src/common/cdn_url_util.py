# @ai-generated
import re
from typing import Optional

from src.config.env_config import EnvConfig


class CdnUrlUtil:
    _cdn_base_url: str = ""

    @classmethod
    def initialize(cls) -> None:
        cls._cdn_base_url = EnvConfig.CDN_IMG_BASE_URL.rstrip("/")

    @classmethod
    def get_cdn_url(cls, path: str, width: Optional[int] = None, height: Optional[int] = None) -> str:
        if not path:
            return ""
        
        if path.startswith("http://") or path.startswith("https://"):
            return cls._apply_image_processing(path, width, height)
        
        normalized_path = path.lstrip("/")
        full_url = f"{cls._cdn_base_url}/{normalized_path}"
        
        return cls._apply_image_processing(full_url, width, height)

    @classmethod
    def _apply_image_processing(cls, url: str, width: Optional[int] = None, height: Optional[int] = None) -> str:
        if not width and not height:
            return url
        
        processed_url = url
        if cls._cdn_base_url and cls._cdn_base_url in url:
            if width:
                processed_url = f"{processed_url}?x-oss-process=image/resize,w_{width}"
                if height:
                    processed_url = f"{processed_url},h_{height}"
            elif height:
                processed_url = f"{processed_url}?x-oss-process=image/resize,h_{height}"
        
        return processed_url

    @classmethod
    def remove_cdn_prefix(cls, url: str) -> str:
        if not url:
            return ""
        
        if url.startswith("http://") or url.startswith("https://"):
            if cls._cdn_base_url in url:
                return url.replace(f"{cls._cdn_base_url}/", "", 1)
            return url
        
        return url

    @classmethod
    def is_cdn_url(cls, url: str) -> bool:
        if not url:
            return False
        if cls._cdn_base_url in url:
            return True
        return url.startswith("http://") or url.startswith("https://")

    @classmethod
    def build_upload_path(cls, prefix: str, filename: str) -> str:
        normalized_prefix = prefix.strip("/")
        normalized_filename = filename.lstrip("/")
        if normalized_prefix:
            return f"{normalized_prefix}/{normalized_filename}"
        return normalized_filename

    @classmethod
    def get_file_extension(cls, filename: str) -> str:
        if "." in filename:
            return filename.rsplit(".", 1)[1].lower()
        return ""

    @classmethod
    def is_image_file(cls, filename: str) -> bool:
        extensions = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "svg"}
        return cls.get_file_extension(filename) in extensions

    @classmethod
    def build_url(cls, path: str, width: Optional[int] = None, height: Optional[int] = None) -> str:
        return cls.get_cdn_url(path, width, height)

    @classmethod
    def build_thumbnail_url(cls, path: str, width: int, height: int = None) -> str:
        return cls.get_cdn_url(path, width, height)