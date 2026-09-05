# @ai-generated
"""
B10 微信支付V3模块单元测试（AsyncMock 模拟，不依赖真实 DB/Redis/微信API）

覆盖范围（目标覆盖率 ≥90%）：
 1. exceptions.py
    - WechatPayError 构造与字段
    - map_wechat_api_error 错误码映射
    - raise_from_http_error HTTP错误状态码映射
 2. signer.py
    - 证书加载（私钥/平台证书）
    - 请求签名生成与验证
    - 回调验签（成功/失败）
    - 回调解密（成功/失败）
    - 认证头生成
 3. client.py
    - POST/GET 请求成功
    - 熔断拦截
    - 超时重试
    - HTTP 4xx 不重试
    - HTTP 5xx 重试
    - 响应解析失败
 4. service.py
    - 单笔转账成功
    - 单笔转账金额转分
    - 批量转账成功（含明细汇总）
    - 批量转账参数校验（空列表/超1000条）
    - 幂等防重复（SETNX 命中）
    - 幂等缓存命中返回已有结果
    - 转账失败清除幂等键
    - 查询批次/明细
    - 回调解析（验签成功→解密→状态映射）
    - 回调验签失败
    - 回调解密失败
"""
import base64
import json
import os
import sys
import tempfile
from decimal import Decimal
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

sys.path.insert(0, ".")

from src.common.wechat_pay.exceptions import (
    WECHAT_PAY_ERROR_CALLBACK_DECRYPT,
    WECHAT_PAY_ERROR_CALLBACK_VERIFY,
    WECHAT_PAY_ERROR_CIRCUIT_BREAKER,
    WECHAT_PAY_ERROR_DUPLICATE,
    WECHAT_PAY_ERROR_HTTP,
    WECHAT_PAY_ERROR_INSUFFICIENT_BALANCE,
    WECHAT_PAY_ERROR_PARAM,
    WECHAT_PAY_ERROR_PARSE,
    WECHAT_PAY_ERROR_SIGN,
    WECHAT_PAY_ERROR_TIMEOUT,
    WechatPayError,
    map_wechat_api_error,
    raise_from_http_error,
)
from src.common.wechat_pay.signer import WechatPaySigner
from src.common.wechat_pay.client import WechatPayClient
from src.common.wechat_pay.service import (
    WechatPayTransferService,
    create_wechat_pay_service,
)
from src.cps.circuit_breaker import BreakerState, CircuitBreaker


# ══════════════════════════════════════════════════════
# 测试用 RSA 密钥对生成（全局共享，避免重复生成开销）
# ══════════════════════════════════════════════════════


def _generate_test_keypair():
    """生成测试用 RSA 2048 密钥对"""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_key, public_key, private_pem, public_pem


# 模块级共享密钥对
_TEST_PRIVATE_KEY, _TEST_PUBLIC_KEY, _TEST_PRIVATE_PEM, _TEST_PUBLIC_PEM = (
    _generate_test_keypair()
)


def _write_temp_key(pem_content: str) -> str:
    """将 PEM 写入临时文件，返回路径"""
    fd, path = tempfile.mkstemp(suffix=".pem")
    with os.fdopen(fd, "w") as f:
        f.write(pem_content)
    return path


# ══════════════════════════════════════════════════════
# 1. exceptions.py 测试
# ══════════════════════════════════════════════════════


class TestWechatPayExceptions:
    """异常定义与错误码映射测试"""

    def test_wechat_pay_error_construction(self):
        """WechatPayError 构造与字段"""
        err = WechatPayError(
            code=20001,
            msg="证书加载失败",
            data={"path": "/tmp/key.pem"},
            wechat_code="CERT_ERROR",
            http_status=400,
        )
        assert err.code == 20001
        assert err.msg == "证书加载失败"
        assert err.data == {"path": "/tmp/key.pem"}
        assert err.wechat_code == "CERT_ERROR"
        assert err.http_status == 400

    def test_wechat_pay_error_inherits_biz_exception(self):
        """WechatPayError 继承 BizException"""
        from src.schemas.cps_goods import BizException

        err = WechatPayError(code=20001, msg="test")
        assert isinstance(err, BizException)

    def test_map_wechat_api_error_known_code(self):
        """已知错误码映射"""
        err = map_wechat_api_error("SIGN_ERROR", "签名错误")
        assert err.code == WECHAT_PAY_ERROR_SIGN
        assert err.wechat_code == "SIGN_ERROR"

    def test_map_wechat_api_error_insufficient_balance(self):
        """余额不足错误映射"""
        err = map_wechat_api_error("NOT_ENOUGH", "余额不足")
        assert err.code == WECHAT_PAY_ERROR_INSUFFICIENT_BALANCE

    def test_map_wechat_api_error_unknown_code(self):
        """未知错误码映射到通用业务错误"""
        err = map_wechat_api_error("UNKNOWN_CODE", "未知错误")
        assert err.code == 20013  # WECHAT_PAY_ERROR_BIZ

    def test_raise_from_http_error_with_code(self):
        """HTTP错误含微信code字段"""
        body = {"code": "SIGN_ERROR", "message": "签名错误"}
        with pytest.raises(WechatPayError) as exc_info:
            raise_from_http_error(400, body)
        assert exc_info.value.code == WECHAT_PAY_ERROR_SIGN

    def test_raise_from_http_error_401(self):
        """HTTP 401 认证失败"""
        with pytest.raises(WechatPayError, match="认证失败"):
            raise_from_http_error(401, None)

    def test_raise_from_http_error_429(self):
        """HTTP 429 限流"""
        with pytest.raises(WechatPayError, match="限流"):
            raise_from_http_error(429, None)

    def test_raise_from_http_error_500(self):
        """HTTP 500 服务端错误"""
        with pytest.raises(WechatPayError, match="服务端错误"):
            raise_from_http_error(500, None)

    def test_raise_from_http_error_other(self):
        """其他HTTP错误"""
        with pytest.raises(WechatPayError, match="请求失败"):
            raise_from_http_error(404, {"error": "not found"})


# ══════════════════════════════════════════════════════
# 2. signer.py 测试
# ══════════════════════════════════════════════════════


class TestWechatPaySigner:
    """签名/验签/解密工具测试"""

    def _make_signer(self) -> WechatPaySigner:
        """创建测试用签名器"""
        key_path = _write_temp_key(_TEST_PRIVATE_PEM)
        return WechatPaySigner(
            mch_id="1234567890",
            serial_no="abcdef1234567890",
            private_key_path=key_path,
        )

    def test_init_success(self):
        """签名器初始化成功"""
        signer = self._make_signer()
        assert signer.mch_id == "1234567890"
        assert signer.serial_no == "abcdef1234567890"

    def test_init_empty_path_raises(self):
        """私钥路径为空抛异常"""
        with pytest.raises(WechatPayError, match="路径为空"):
            WechatPaySigner("mch", "serial", "")

    def test_init_file_not_exists_raises(self):
        """私钥文件不存在抛异常"""
        with pytest.raises(WechatPayError, match="文件不存在"):
            WechatPaySigner("mch", "serial", "/nonexistent/path.pem")

    def test_generate_request_signature(self):
        """请求签名生成"""
        signer = self._make_signer()
        sig, ts, nonce = signer.generate_request_signature(
            "POST", "/v3/transfer/batches", '{"key":"value"}'
        )
        assert sig  # 非空
        assert ts  # 非空
        assert len(nonce) == 32  # uuid4 hex

    def test_generate_request_signature_with_custom_ts_nonce(self):
        """自定义时间戳和随机串"""
        signer = self._make_signer()
        sig, ts, nonce = signer.generate_request_signature(
            "GET", "/v3/transfer/batches", "", timestamp="1234567890", nonce="abc123"
        )
        assert ts == "1234567890"
        assert nonce == "abc123"

    def test_verify_callback_signature_success(self):
        """回调验签成功"""
        signer = self._make_signer()
        # 用私钥签名
        timestamp = "1234567890"
        nonce = "testnonce123"
        body = '{"event":"transfer"}'
        verify_str = f"{timestamp}\n{nonce}\n{body}\n"
        signature = base64.b64encode(
            _TEST_PRIVATE_KEY.sign(
                verify_str.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        ).decode("utf-8")

        # 用公钥验签
        result = WechatPaySigner.verify_callback_signature(
            platform_cert_pem=_TEST_PUBLIC_PEM,
            timestamp=timestamp,
            nonce=nonce,
            body=body,
            signature=signature,
        )
        assert result is True

    def test_verify_callback_signature_fail(self):
        """回调验签失败（错误签名）"""
        result = WechatPaySigner.verify_callback_signature(
            platform_cert_pem=_TEST_PUBLIC_PEM,
            timestamp="123",
            nonce="abc",
            body="test",
            signature="invalid_base64_signature",
        )
        assert result is False

    def test_verify_callback_empty_cert_raises(self):
        """平台证书为空抛异常"""
        with pytest.raises(WechatPayError, match="为空"):
            WechatPaySigner.verify_callback_signature(
                platform_cert_pem="",
                timestamp="123",
                nonce="abc",
                body="test",
                signature="sig",
            )

    def test_decrypt_callback_resource_success(self):
        """回调解密成功"""
        # 用 AES-GCM 加密测试数据
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        api_v3_key = "0123456789abcdef0123456789abcdef"  # 32字节
        nonce = "0123456789ab"
        associated_data = "transfer"
        plaintext = '{"out_batch_no":"B001","batch_status":"FINISHED"}'

        aesgcm = AESGCM(api_v3_key.encode("utf-8"))
        ciphertext_bytes = aesgcm.encrypt(
            nonce.encode("utf-8"),
            plaintext.encode("utf-8"),
            associated_data.encode("utf-8"),
        )
        ciphertext_b64 = base64.b64encode(ciphertext_bytes).decode("utf-8")

        result = WechatPaySigner.decrypt_callback_resource(
            api_v3_key=api_v3_key,
            associated_data=associated_data,
            nonce=nonce,
            ciphertext=ciphertext_b64,
        )
        assert result == plaintext

    def test_decrypt_callback_empty_key_raises(self):
        """APIv3密钥为空抛异常"""
        with pytest.raises(WechatPayError, match="为空"):
            WechatPaySigner.decrypt_callback_resource(
                api_v3_key="",
                associated_data="",
                nonce="abc",
                ciphertext="xxx",
            )

    def test_decrypt_callback_wrong_key_length_raises(self):
        """APIv3密钥长度不对抛异常"""
        with pytest.raises(WechatPayError, match="长度必须为32"):
            WechatPaySigner.decrypt_callback_resource(
                api_v3_key="short",
                associated_data="",
                nonce="abc",
                ciphertext="xxx",
            )

    def test_decrypt_callback_wrong_key_raises(self):
        """解密失败（错误密钥）"""
        with pytest.raises(WechatPayError, match="解密失败"):
            WechatPaySigner.decrypt_callback_resource(
                api_v3_key="0123456789abcdef0123456789abcdef",
                associated_data="",
                nonce="0123456789ab",
                ciphertext="invalid_base64",
            )

    def test_build_authorization_header(self):
        """认证头生成"""
        signer = self._make_signer()
        auth = signer.build_authorization_header(
            "POST", "/v3/transfer/batches", '{"key":"value"}'
        )
        assert auth.startswith("WECHATPAY2-SHA256-RSA2048 ")
        assert 'mchid="1234567890"' in auth
        assert 'serial_no="abcdef1234567890"' in auth
        assert "signature=" in auth

    def test_load_platform_cert_from_public_key(self):
        """从公钥PEM加载平台证书"""
        key = WechatPaySigner.load_platform_cert(_TEST_PUBLIC_PEM)
        assert key is not None

    def test_load_platform_cert_empty_raises(self):
        """平台证书为空抛异常"""
        with pytest.raises(WechatPayError, match="为空"):
            WechatPaySigner.load_platform_cert("")

    def test_load_platform_cert_invalid_raises(self):
        """无效PEM抛异常"""
        with pytest.raises(WechatPayError, match="加载平台证书失败"):
            WechatPaySigner.load_platform_cert("invalid_pem_content")

    def test_load_platform_cert_from_x509_certificate(self):
        """从 x509 证书加载平台证书"""
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes
        from datetime import datetime, timedelta

        # 构造自签名 x509 证书
        subject = issuer = x509.Name(
            [x509.NameAttribute(x509.NameOID.COMMON_NAME, "test")]
        )
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(_TEST_PUBLIC_KEY)
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=1))
            .sign(_TEST_PRIVATE_KEY, hashes.SHA256())
        )
        cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
        key = WechatPaySigner.load_platform_cert(cert_pem)
        assert key is not None

    def test_load_private_key_invalid_pem_raises(self):
        """加载无效私钥文件抛异常"""
        invalid_path = _write_temp_key("not a valid pem")
        with pytest.raises(WechatPayError, match="加载商户私钥失败"):
            WechatPaySigner("mch", "serial", invalid_path)

    def test_load_private_key_ec_key_raises(self):
        """加载非 RSA 私钥抛异常"""
        from cryptography.hazmat.primitives.asymmetric import ec

        ec_key = ec.generate_private_key(ec.SECP256R1())
        ec_pem = ec_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        ec_path = _write_temp_key(ec_pem)
        with pytest.raises(WechatPayError, match="不是 RSA 类型"):
            WechatPaySigner("mch", "serial", ec_path)

    @pytest.mark.asyncio
    async def test_verify_callback_cert_load_fail_raises(self):
        """回调验签时证书加载失败抛异常"""
        with pytest.raises(WechatPayError, match="为空"):
            WechatPaySigner.verify_callback_signature(
                platform_cert_pem="",
                timestamp="123",
                nonce="abc",
                body="test",
                signature="sig",
            )

    @pytest.mark.asyncio
    async def test_verify_callback_invalid_cert_raises(self):
        """回调验签时证书无效抛异常"""
        with pytest.raises(WechatPayError, match="加载平台证书失败"):
            WechatPaySigner.verify_callback_signature(
                platform_cert_pem="invalid_pem",
                timestamp="123",
                nonce="abc",
                body="test",
                signature="sig",
            )


# ══════════════════════════════════════════════════════
# 3. client.py 测试
# ══════════════════════════════════════════════════════


class TestWechatPayClient:
    """HTTP客户端测试"""

    def _make_client(self, breaker: Optional[MagicMock] = None) -> WechatPayClient:
        """创建测试用客户端"""
        key_path = _write_temp_key(_TEST_PRIVATE_PEM)
        signer = WechatPaySigner("mch", "serial", key_path)
        if breaker is None:
            breaker = MagicMock()
            breaker.allow_request = AsyncMock(return_value=True)
            breaker.record_success = AsyncMock(return_value=None)
            breaker.record_failure = AsyncMock(return_value=None)
        return WechatPayClient(signer, circuit_breaker=breaker, max_retry=2)

    @pytest.mark.asyncio
    async def test_post_success(self):
        """POST 请求成功"""
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"batch_id":"B123"}'
        mock_response.json.return_value = {"batch_id": "B123"}

        with patch("src.common.wechat_pay.client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance

            result = await client.post("/v3/transfer/batches", {"key": "value"})

        assert result == {"batch_id": "B123"}

    @pytest.mark.asyncio
    async def test_get_success(self):
        """GET 请求成功"""
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"batch_status":"FINISHED"}'
        mock_response.json.return_value = {"batch_status": "FINISHED"}

        with patch("src.common.wechat_pay.client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance

            result = await client.get("/v3/transfer/batches/batch-id/B123")

        assert result == {"batch_status": "FINISHED"}

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocked(self):
        """熔断拦截"""
        breaker = MagicMock()
        breaker.allow_request = AsyncMock(return_value=False)
        client = self._make_client(breaker=breaker)

        with pytest.raises(WechatPayError, match="熔断降级"):
            await client.post("/v3/test", {})

    @pytest.mark.asyncio
    async def test_http_4xx_no_retry(self):
        """HTTP 4xx 不重试直接抛"""
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"code":"PARAM_ERROR","message":"参数错误"}'
        mock_response.json.return_value = {"code": "PARAM_ERROR", "message": "参数错误"}

        call_count = 0

        with patch("src.common.wechat_pay.client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance

            with pytest.raises(WechatPayError) as exc_info:
                await client.post("/v3/test", {})
            assert exc_info.value.http_status == 400
            # 只调用一次（不重试）
            assert mock_instance.post.await_count == 1

    @pytest.mark.asyncio
    async def test_http_500_retry(self):
        """HTTP 5xx 重试"""
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = '{"code":"SYSTEM_ERROR","message":"系统错误"}'
        mock_response.json.return_value = {
            "code": "SYSTEM_ERROR",
            "message": "系统错误",
        }

        with patch("src.common.wechat_pay.client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance

            with patch("src.common.wechat_pay.client.asyncio.sleep", new=AsyncMock()):
                with pytest.raises(WechatPayError):
                    await client.post("/v3/test", {})
            # 重试2次 + 首次 = 3次
            assert mock_instance.post.await_count == 3

    @pytest.mark.asyncio
    async def test_timeout_retry(self):
        """超时重试"""
        import httpx

        client = self._make_client()

        with patch("src.common.wechat_pay.client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(
                side_effect=httpx.TimeoutException("timeout")
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance

            with patch("src.common.wechat_pay.client.asyncio.sleep", new=AsyncMock()):
                with pytest.raises(WechatPayError, match="超时"):
                    await client.post("/v3/test", {})
            assert mock_instance.post.await_count == 3

    @pytest.mark.asyncio
    async def test_connect_error_retry(self):
        """连接失败重试"""
        import httpx

        client = self._make_client()

        with patch("src.common.wechat_pay.client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(
                side_effect=httpx.ConnectError("connect failed")
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance

            with patch("src.common.wechat_pay.client.asyncio.sleep", new=AsyncMock()):
                with pytest.raises(WechatPayError, match="连接失败"):
                    await client.post("/v3/test", {})

    @pytest.mark.asyncio
    async def test_json_parse_error(self):
        """响应JSON解析失败"""
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "invalid json"
        mock_response.json.side_effect = ValueError("not json")

        with patch("src.common.wechat_pay.client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance

            with pytest.raises(WechatPayError, match="JSON解析失败"):
                await client.post("/v3/test", {})

    @pytest.mark.asyncio
    async def test_empty_response_body(self):
        """空响应体返回空dict"""
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.text = ""

        with patch("src.common.wechat_pay.client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance

            result = await client.post("/v3/test", {})
        assert result == {}


# ══════════════════════════════════════════════════════
# 4. service.py 测试
# ══════════════════════════════════════════════════════


class TestWechatPayTransferService:
    """转账业务服务测试"""

    def _make_service(self) -> WechatPayTransferService:
        """创建测试用服务（mock client）"""
        mock_client = MagicMock()
        mock_client.signer = MagicMock()
        mock_client.post = AsyncMock()
        mock_client.get = AsyncMock()
        return WechatPayTransferService(mock_client)

    @pytest.mark.asyncio
    async def test_transfer_single_success(self):
        """单笔转账成功"""
        svc = self._make_service()
        svc.client.post = AsyncMock(
            return_value={
                "batch_id": "wx_batch_001",
                "create_time": "2026-08-02T12:00:00",
            }
        )

        with patch(
            "src.common.wechat_pay.service.RedisClient.setnx",
            new=AsyncMock(return_value=True),
        ):
            with patch(
                "src.common.wechat_pay.service.RedisClient.expire",
                new=AsyncMock(return_value=True),
            ):
                with patch(
                    "src.common.wechat_pay.service.RedisClient.set",
                    new=AsyncMock(return_value=True),
                ):
                    result = await svc.transfer_single(
                        out_batch_no="BATCH001",
                        out_detail_no="DETAIL001",
                        transfer_amount=Decimal("100.00"),
                        openid="oX1234567890",
                        transfer_remark="佣金提现",
                    )

        assert result["batch_id"] == "wx_batch_001"
        assert result["out_batch_no"] == "BATCH001"
        assert result["status"] == "ACCEPTED"

    @pytest.mark.asyncio
    async def test_transfer_single_zero_amount_raises(self):
        """转账金额为0抛异常"""
        svc = self._make_service()
        with pytest.raises(WechatPayError, match="必须大于0"):
            await svc.transfer_single(
                out_batch_no="BATCH001",
                out_detail_no="DETAIL001",
                transfer_amount=Decimal("0"),
                openid="oX123",
                transfer_remark="test",
            )

    @pytest.mark.asyncio
    async def test_transfer_single_negative_amount_raises(self):
        """转账金额为负抛异常"""
        svc = self._make_service()
        with pytest.raises(WechatPayError, match="必须大于0"):
            await svc.transfer_single(
                out_batch_no="BATCH001",
                out_detail_no="DETAIL001",
                transfer_amount=Decimal("-10"),
                openid="oX123",
                transfer_remark="test",
            )

    @pytest.mark.asyncio
    async def test_transfer_single_idempotent_duplicate(self):
        """幂等防重复（SETNX未获取）"""
        svc = self._make_service()
        with patch(
            "src.common.wechat_pay.service.RedisClient.setnx",
            new=AsyncMock(return_value=False),
        ):
            with patch(
                "src.common.wechat_pay.service.RedisClient.get",
                new=AsyncMock(return_value=None),
            ):
                with pytest.raises(WechatPayError, match="已存在或正在处理中"):
                    await svc.transfer_single(
                        out_batch_no="BATCH001",
                        out_detail_no="DETAIL001",
                        transfer_amount=Decimal("100"),
                        openid="oX123",
                        transfer_remark="test",
                    )

    @pytest.mark.asyncio
    async def test_transfer_single_idempotent_cache_hit(self):
        """幂等缓存命中返回已有结果"""
        svc = self._make_service()
        cached_data = {
            "batch_id": "wx_batch_001",
            "out_batch_no": "BATCH001",
            "status": "ACCEPTED",
        }
        with patch(
            "src.common.wechat_pay.service.RedisClient.setnx",
            new=AsyncMock(return_value=False),
        ):
            with patch(
                "src.common.wechat_pay.service.RedisClient.get",
                new=AsyncMock(return_value=json.dumps(cached_data)),
            ):
                result = await svc.transfer_single(
                    out_batch_no="BATCH001",
                    out_detail_no="DETAIL001",
                    transfer_amount=Decimal("100"),
                    openid="oX123",
                    transfer_remark="test",
                )
        assert result["batch_id"] == "wx_batch_001"
        # client.post 不应被调用
        svc.client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_transfer_single_api_fail_clears_idempotent(self):
        """转账API失败清除幂等键"""
        svc = self._make_service()
        svc.client.post = AsyncMock(
            side_effect=WechatPayError(code=20004, msg="API失败")
        )

        with patch(
            "src.common.wechat_pay.service.RedisClient.setnx",
            new=AsyncMock(return_value=True),
        ):
            with patch(
                "src.common.wechat_pay.service.RedisClient.expire",
                new=AsyncMock(return_value=True),
            ):
                with patch(
                    "src.common.wechat_pay.service.RedisClient.delete",
                    new=AsyncMock(return_value=1),
                ) as mock_del:
                    with pytest.raises(WechatPayError, match="API失败"):
                        await svc.transfer_single(
                            out_batch_no="BATCH001",
                            out_detail_no="DETAIL001",
                            transfer_amount=Decimal("100"),
                            openid="oX123",
                            transfer_remark="test",
                        )
        mock_del.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_transfer_batch_success(self):
        """批量转账成功"""
        svc = self._make_service()
        svc.client.post = AsyncMock(
            return_value={
                "batch_id": "wx_batch_002",
                "create_time": "2026-08-02T12:00:00",
            }
        )
        details = [
            {
                "out_detail_no": "D001",
                "transfer_amount": Decimal("100.00"),
                "openid": "oX001",
                "transfer_remark": "提现1",
            },
            {
                "out_detail_no": "D002",
                "transfer_amount": Decimal("200.00"),
                "openid": "oX002",
                "transfer_remark": "提现2",
            },
        ]

        with patch(
            "src.common.wechat_pay.service.RedisClient.setnx",
            new=AsyncMock(return_value=True),
        ):
            with patch(
                "src.common.wechat_pay.service.RedisClient.expire",
                new=AsyncMock(return_value=True),
            ):
                with patch(
                    "src.common.wechat_pay.service.RedisClient.set",
                    new=AsyncMock(return_value=True),
                ):
                    result = await svc.transfer_batch(
                        out_batch_no="BATCH002",
                        batch_name="批量提现",
                        details=details,
                    )

        assert result["batch_id"] == "wx_batch_002"
        # 验证请求体包含正确的汇总金额（300元=30000分）
        call_args = svc.client.post.call_args
        body = call_args[0][1]
        assert body["total_amount"] == 30000
        assert body["total_num"] == 2

    @pytest.mark.asyncio
    async def test_transfer_batch_empty_details_raises(self):
        """批量转账空明细列表抛异常"""
        svc = self._make_service()
        with pytest.raises(WechatPayError, match="不能为空"):
            await svc.transfer_batch("BATCH", "name", [])

    @pytest.mark.asyncio
    async def test_transfer_batch_too_many_details_raises(self):
        """批量转账超1000条抛异常"""
        svc = self._make_service()
        details = [
            {"out_detail_no": f"D{i}", "transfer_amount": Decimal("1"), "openid": "oX"}
            for i in range(1001)
        ]
        with pytest.raises(WechatPayError, match="不能超过1000"):
            await svc.transfer_batch("BATCH", "name", details)

    @pytest.mark.asyncio
    async def test_query_batch(self):
        """查询批次"""
        svc = self._make_service()
        svc.client.get = AsyncMock(
            return_value={"batch_id": "B123", "batch_status": "FINISHED"}
        )
        result = await svc.query_batch("B123")
        assert result["batch_status"] == "FINISHED"

    @pytest.mark.asyncio
    async def test_query_batch_with_detail(self):
        """查询批次含明细"""
        svc = self._make_service()
        svc.client.get = AsyncMock(
            return_value={
                "batch_id": "B123",
                "batch_status": "FINISHED",
                "transfer_detail_list": [],
            }
        )
        await svc.query_batch("B123", need_query_detail=True)
        call_args = svc.client.get.call_args
        path = call_args[0][0]
        assert "need_query_detail=true" in path

    @pytest.mark.asyncio
    async def test_query_detail(self):
        """查询单笔明细"""
        svc = self._make_service()
        svc.client.get = AsyncMock(
            return_value={"detail_id": "D123", "detail_status": "FINISHED"}
        )
        result = await svc.query_detail("B123", "D123")
        assert result["detail_status"] == "FINISHED"

    @pytest.mark.asyncio
    async def test_parse_callback_success(self):
        """回调解析成功（验签→解密→状态映射）"""
        svc = self._make_service()

        # 构造解密后的数据
        decrypt_data = {
            "out_batch_no": "BATCH001",
            "batch_id": "wx_batch_001",
            "out_detail_no": "D001",
            "detail_id": "wx_d001",
            "batch_status": "FINISHED",
            "fail_reason": "",
        }
        decrypt_json = json.dumps(decrypt_data)

        # 构造回调通知体
        notification = {
            "id": "evt_001",
            "resource": {
                "algorithm": "AEAD_AES_256_GCM",
                "associated_data": "transfer",
                "nonce": "0123456789ab",
                "ciphertext": "fake_ciphertext",
            },
        }
        body = json.dumps(notification)

        # 生成验签签名
        timestamp = "1234567890"
        nonce = "testnonce"
        verify_str = f"{timestamp}\n{nonce}\n{body}\n"
        signature = base64.b64encode(
            _TEST_PRIVATE_KEY.sign(
                verify_str.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        ).decode("utf-8")

        with patch.object(
            WechatPaySigner,
            "decrypt_callback_resource",
            return_value=decrypt_json,
        ):
            result = await svc.parse_callback(
                timestamp=timestamp,
                nonce=nonce,
                body=body,
                signature=signature,
                platform_cert_pem=_TEST_PUBLIC_PEM,
                api_v3_key="0123456789abcdef0123456789abcdef",
            )

        assert result["out_batch_no"] == "BATCH001"
        assert result["batch_id"] == "wx_batch_001"
        assert result["transfer_status"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_parse_callback_verify_fail(self):
        """回调验签失败"""
        svc = self._make_service()
        with pytest.raises(WechatPayError, match="验签失败"):
            await svc.parse_callback(
                timestamp="123",
                nonce="abc",
                body="test",
                signature="invalid_sig",
                platform_cert_pem=_TEST_PUBLIC_PEM,
                api_v3_key="0123456789abcdef0123456789abcdef",
            )

    @pytest.mark.asyncio
    async def test_parse_callback_invalid_json(self):
        """回调通知体JSON解析失败"""
        svc = self._make_service()

        # 生成验签签名（对invalid json签名）
        timestamp = "1234567890"
        nonce = "testnonce"
        body = "invalid json"
        verify_str = f"{timestamp}\n{nonce}\n{body}\n"
        signature = base64.b64encode(
            _TEST_PRIVATE_KEY.sign(
                verify_str.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        ).decode("utf-8")

        with pytest.raises(WechatPayError, match="JSON解析失败"):
            await svc.parse_callback(
                timestamp=timestamp,
                nonce=nonce,
                body=body,
                signature=signature,
                platform_cert_pem=_TEST_PUBLIC_PEM,
                api_v3_key="0123456789abcdef0123456789abcdef",
            )

    @pytest.mark.asyncio
    async def test_parse_callback_no_resource(self):
        """回调通知缺少resource字段"""
        svc = self._make_service()

        body = json.dumps({"id": "evt_001"})  # 无 resource
        timestamp = "1234567890"
        nonce = "testnonce"
        verify_str = f"{timestamp}\n{nonce}\n{body}\n"
        signature = base64.b64encode(
            _TEST_PRIVATE_KEY.sign(
                verify_str.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        ).decode("utf-8")

        with pytest.raises(WechatPayError, match="缺少 resource"):
            await svc.parse_callback(
                timestamp=timestamp,
                nonce=nonce,
                body=body,
                signature=signature,
                platform_cert_pem=_TEST_PUBLIC_PEM,
                api_v3_key="0123456789abcdef0123456789abcdef",
            )

    def test_yuan_to_fen_normal(self):
        """元转分正常"""
        assert WechatPayTransferService._yuan_to_fen(Decimal("100.00")) == 10000
        assert WechatPayTransferService._yuan_to_fen(Decimal("0.01")) == 1
        assert WechatPayTransferService._yuan_to_fen(Decimal("99.99")) == 9999

    def test_yuan_to_fen_zero_raises(self):
        """元转分金额为0抛异常"""
        with pytest.raises(WechatPayError, match="必须大于0"):
            WechatPayTransferService._yuan_to_fen(Decimal("0"))

    def test_yuan_to_fen_negative_raises(self):
        """元转分金额为负抛异常"""
        with pytest.raises(WechatPayError, match="必须大于0"):
            WechatPayTransferService._yuan_to_fen(Decimal("-1"))

    def test_yuan_to_fen_invalid_raises(self):
        """元转分非法值抛异常"""
        with pytest.raises(WechatPayError, match="转换失败"):
            WechatPayTransferService._yuan_to_fen("not_a_number")


# ══════════════════════════════════════════════════════
# 5. create_wechat_pay_service 工厂方法测试
# ══════════════════════════════════════════════════════


class TestCreateWechatPayService:
    """工厂方法测试"""

    @pytest.mark.asyncio
    async def test_create_service_no_config_raises(self):
        """无启用配置抛异常"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "src.common.wechat_pay.service.DatabaseManager.get_session"
        ) as mock_get_session:
            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_cm

            with pytest.raises(WechatPayError, match="无启用配置"):
                await create_wechat_pay_service()

    @pytest.mark.asyncio
    async def test_create_service_invalid_key_path_raises(self):
        """证书路径无效抛异常"""
        mock_config = MagicMock()
        mock_config.mch_id = "123"
        mock_config.serial_no = "serial"
        mock_config.private_key_path = "/nonexistent/key.pem"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "src.common.wechat_pay.service.DatabaseManager.get_session"
        ) as mock_get_session:
            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_cm

            with pytest.raises(WechatPayError, match="文件不存在"):
                await create_wechat_pay_service()

    @pytest.mark.asyncio
    async def test_create_service_success(self):
        """工厂方法创建成功"""
        key_path = _write_temp_key(_TEST_PRIVATE_PEM)
        mock_config = MagicMock()
        mock_config.mch_id = "1234567890"
        mock_config.serial_no = "serial123"
        mock_config.private_key_path = key_path

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "src.common.wechat_pay.service.DatabaseManager.get_session"
        ) as mock_get_session:
            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_cm

            service = await create_wechat_pay_service()
            assert isinstance(service, WechatPayTransferService)
