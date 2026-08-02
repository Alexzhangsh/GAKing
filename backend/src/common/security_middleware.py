# @ai-generated
import re
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.common.log_util import LogConfig


class SecurityMiddleware(BaseHTTPMiddleware):
    _logger = LogConfig.get_logger("security")
    
    _sql_injection_patterns = [
        r"(?i)(select|insert|update|delete|drop|union|exec|execute|xp_|sp_|0x)",
        r"(?i)'(\s+or\s+)?(\d+\s*=\s*\d+)",
        r"(?i)\b(and|or)\b\s*\d+\s*=\s*\d+",
    ]
    
    _xss_patterns = [
        r"(?i)<script[^>]*>.*?</script>",
        r"(?i)on\w+\s*=\s*['\"].*?['\"]",
        r"(?i)javascript:",
        r"(?i)data:",
    ]
    
    _path_traversal_patterns = [
        r"\.\./",
        r"\.\.\\",
        r"/etc/passwd",
        r"/etc/shadow",
    ]

    async def dispatch(self, request: Request, call_next):
        try:
            await self._validate_request(request)
            
            response = await call_next(request)
            return response
            
        except HTTPException as exc:
            self._logger.warning(f"Security violation: {exc.detail}")
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": exc.detail},
            )
        except Exception as e:
            import traceback
            self._logger.error(f"Security middleware error: {str(e)}\n{traceback.format_exc()}")
            return JSONResponse(
                status_code=500,
                content={"error": f"Internal server error: {str(e)}"},
            )

    async def _validate_request(self, request: Request):
        await self._validate_path(request.url.path)
        await self._validate_query_params(request.query_params)

    async def _validate_path(self, path: str):
        for pattern in self._path_traversal_patterns:
            if re.search(pattern, path):
                raise HTTPException(status_code=403, detail="Path traversal detected")

    async def _validate_query_params(self, params):
        for key, value in params.items():
            await self._validate_value(str(key), "query")
            await self._validate_value(str(value), "query")

    async def _validate_body(self, body):
        if isinstance(body, dict):
            for key, value in body.items():
                await self._validate_value(str(key), "body")
                if isinstance(value, str):
                    await self._validate_value(value, "body")
                elif isinstance(value, dict):
                    await self._validate_body(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            await self._validate_value(item, "body")
                        elif isinstance(item, dict):
                            await self._validate_body(item)

    async def _validate_value(self, value: str, source: str):
        for pattern in self._sql_injection_patterns:
            if re.search(pattern, value):
                self._logger.warning(f"SQL injection detected in {source}: {value}")
                raise HTTPException(status_code=403, detail="SQL injection detected")
        
        for pattern in self._xss_patterns:
            if re.search(pattern, value):
                self._logger.warning(f"XSS detected in {source}: {value}")
                raise HTTPException(status_code=403, detail="XSS detected")