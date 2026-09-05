# @ai-generated
"""
微信支付V3证书加载、签名、验签工具（B10 新建）

职责：
1. 加载商户私钥（PEM 格式，从 private_key_path 读取）
2. 生成请求签名（SHA256-with-RSA）
3. 验证微信回调签名（使用微信平台证书公钥）
4. 解密回调密文（AEAD_AES_256_GCM，使用 APIv3 密钥）

签名算法（微信支付V3规范）：
  请求签名串 = HTTP方法\n请求URL\n时间戳\n随机串\n请求体\n
  签名 = base64(RSA-SHA256(签名串, 商户私钥))

验签算法：
  验签串 = 时间戳\n随机串\n响应体\n
  验证 = RSA-SHA256-VERIFY(验签串, 微信平台证书公钥, 微信签名)

约束：不修改 B01-B09 基线代码；复用 cryptography 库
"""
import base64
import logging
import os
import time
import uuid
from typing import Optional, Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.common.wechat_pay.exceptions import (
    WECHAT_PAY_ERROR_CALLBACK_DECRYPT,
    WECHAT_PAY_ERROR_CALLBACK_VERIFY,
    WECHAT_PAY_ERROR_CERT_LOAD,
    WECHAT_PAY_ERROR_SIGN,
    WechatPayError,
)

logger = logging.getLogger("common.wechat_pay.signer")


class WechatPaySigner:
    """微信支付V3签名/验签工具

    商户私钥在构造时加载（从文件路径读取 PEM）；微信平台证书动态加载（验签时传入 PEM 字符串）。
    线程安全：私钥/公钥对象不可变，多请求共享同一实例。
    """

    def __init__(self, mch_id: str, serial_no: str, private_key_path: str) -> None:
        """初始化签名器

        Args:
            mch_id: 微信商户号
            serial_no: 商户证书序列号
            private_key_path: 商户私钥 PEM 文件路径
        Raises:
            WechatPayError: 证书加载失败
        """
        self.mch_id = mch_id
        self.serial_no = serial_no
        self._private_key = self._load_private_key(private_key_path)
        logger.info(
            "[wechat_pay_signer] 初始化成功 mch_id=%s serial_no=%s",
            mch_id,
            serial_no[:8] + "..." if len(serial_no) > 8 else serial_no,
        )

    # ── 证书加载 ────────────────────────────────────────

    @staticmethod
    def _load_private_key(private_key_path: str):
        """加载商户私钥（PEM 格式）

        Args:
            private_key_path: 私钥文件路径
        Returns:
            RSAPrivateKey 对象
        Raises:
            WechatPayError: 文件不存在 / 解析失败
        """
        if not private_key_path:
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_CERT_LOAD,
                msg="商户私钥路径为空",
            )
        if not os.path.exists(private_key_path):
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_CERT_LOAD,
                msg=f"商户私钥文件不存在: {private_key_path}",
            )
        try:
            with open(private_key_path, "rb") as f:
                pem_data = f.read()
            key = serialization.load_pem_private_key(pem_data, password=None)
            if not isinstance(key, rsa.RSAPrivateKey):
                raise WechatPayError(
                    code=WECHAT_PAY_ERROR_CERT_LOAD,
                    msg="私钥不是 RSA 类型",
                )
            return key
        except WechatPayError:
            raise
        except Exception as e:
            logger.error(
                "[wechat_pay_signer] 加载商户私钥失败 path=%s: %s",
                private_key_path,
                e,
                exc_info=True,
            )
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_CERT_LOAD,
                msg=f"加载商户私钥失败: {e}",
            )

    @staticmethod
    def load_platform_cert(pem_str: str):
        """加载微信平台证书公钥（用于验签）

        Args:
            pem_str: PEM 格式证书字符串
        Returns:
            RSAPublicKey 对象
        Raises:
            WechatPayError: 解析失败
        """
        if not pem_str:
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_CERT_LOAD,
                msg="平台证书 PEM 为空",
            )
        try:
            # 尝试作为证书加载
            from cryptography import x509

            cert = x509.load_pem_x509_certificate(pem_str.encode("utf-8"))
            return cert.public_key()
        except Exception:
            pass
        # 尝试作为公钥直接加载
        try:
            key = serialization.load_pem_public_key(pem_str.encode("utf-8"))
            if isinstance(key, rsa.RSAPublicKey):
                return key
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_CERT_LOAD,
                msg="平台证书公钥不是 RSA 类型",
            )
        except WechatPayError:
            raise
        except Exception as e:
            logger.error("[wechat_pay_signer] 加载平台证书失败: %s", e, exc_info=True)
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_CERT_LOAD,
                msg=f"加载平台证书失败: {e}",
            )

    # ── 请求签名 ────────────────────────────────────────

    def generate_request_signature(
        self,
        method: str,
        url: str,
        body: str,
        *,
        timestamp: Optional[str] = None,
        nonce: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """生成微信支付V3请求签名

        签名串格式：
            {method}\n{url}\n{timestamp}\n{nonce}\n{body}\n

        Args:
            method: HTTP 方法（GET / POST / PUT）
            url: 请求 URL（含 query string，不含域名）
            body: 请求体（GET 请求传空字符串）
            timestamp: 时间戳（秒），None 自动生成
            nonce: 随机串，None 自动生成
        Returns:
            (signature, timestamp, nonce) 签名值 + 时间戳 + 随机串
        Raises:
            WechatPayError: 签名计算失败
        """
        if timestamp is None:
            timestamp = str(int(time.time()))
        if nonce is None:
            nonce = uuid.uuid4().hex

        # 构造签名串
        sign_str = f"{method.upper()}\n{url}\n{timestamp}\n{nonce}\n{body}\n"

        try:
            signature = self._rsa_sign(sign_str)
            logger.debug(
                "[wechat_pay_signer] 请求签名成功 method=%s url=%s",
                method,
                url,
            )
            return signature, timestamp, nonce
        except WechatPayError:
            raise
        except Exception as e:
            logger.error("[wechat_pay_signer] 请求签名失败: %s", e, exc_info=True)
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_SIGN,
                msg=f"请求签名计算失败: {e}",
            )

    def _rsa_sign(self, sign_str: str) -> str:
        """RSA-SHA256 签名并 base64 编码"""
        try:
            signature = self._private_key.sign(
                sign_str.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return base64.b64encode(signature).decode("utf-8")
        except Exception as e:
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_SIGN,
                msg=f"RSA 签名失败: {e}",
            )

    # ── 回调验签 ────────────────────────────────────────

    @staticmethod
    def verify_callback_signature(
        platform_cert_pem: str,
        timestamp: str,
        nonce: str,
        body: str,
        signature: str,
    ) -> bool:
        """验证微信回调通知签名

        验签串格式：
            {timestamp}\n{nonce}\n{body}\n

        Args:
            platform_cert_pem: 微信平台证书 PEM 字符串
            timestamp: 回调请求头 Wechatpay-Timestamp
            nonce: 回调请求头 Wechatpay-Nonce
            body: 回调请求体原文
            signature: 回调请求头 Wechatpay-Signature（base64）
        Returns:
            True 验签通过 / False 验签失败
        Raises:
            WechatPayError: 证书加载失败
        """
        try:
            public_key = WechatPaySigner.load_platform_cert(platform_cert_pem)
        except WechatPayError:
            raise

        verify_str = f"{timestamp}\n{nonce}\n{body}\n"

        try:
            sig_bytes = base64.b64decode(signature)
            public_key.verify(
                sig_bytes,
                verify_str.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            logger.info("[wechat_pay_signer] 回调验签通过")
            return True
        except Exception as e:
            logger.warning("[wechat_pay_signer] 回调验签失败: %s", e)
            return False

    # ── 回调解密 ────────────────────────────────────────

    @staticmethod
    def decrypt_callback_resource(
        api_v3_key: str,
        associated_data: str,
        nonce: str,
        ciphertext: str,
    ) -> str:
        """解密微信回调通知中的 resource.ciphertext（AEAD_AES_256_GCM）

        微信回调通知体示例：
            {
                "resource": {
                    "algorithm": "AEAD_AES_256_GCM",
                    "associated_data": "transfer",
                    "nonce": "xxxxx",
                    "ciphertext": "base64密文"
                }
            }

        Args:
            api_v3_key: APIv3 密钥（32字节）
            associated_data: 附加数据
            nonce: 随机串
            ciphertext: base64 编码的密文
        Returns:
            解密后的 JSON 字符串
        Raises:
            WechatPayError: 解密失败
        """
        if not api_v3_key:
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_CALLBACK_DECRYPT,
                msg="APIv3 密钥为空",
            )
        if len(api_v3_key) != 32:
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_CALLBACK_DECRYPT,
                msg=f"APIv3 密钥长度必须为32字节，当前 {len(api_v3_key)}",
            )

        try:
            key_bytes = api_v3_key.encode("utf-8")
            nonce_bytes = nonce.encode("utf-8")
            ciphertext_bytes = base64.b64decode(ciphertext)
            associated_data_bytes = (
                associated_data.encode("utf-8") if associated_data else b""
            )

            aesgcm = AESGCM(key_bytes)
            plaintext = aesgcm.decrypt(
                nonce_bytes, ciphertext_bytes, associated_data_bytes
            )
            result = plaintext.decode("utf-8")
            logger.info("[wechat_pay_signer] 回调解密成功")
            return result
        except WechatPayError:
            raise
        except Exception as e:
            logger.error("[wechat_pay_signer] 回调解密失败: %s", e, exc_info=True)
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_CALLBACK_DECRYPT,
                msg=f"回调解密失败: {e}",
            )

    # ── 认证头生成 ──────────────────────────────────────

    def build_authorization_header(
        self,
        method: str,
        url: str,
        body: str,
    ) -> str:
        """生成 Authorization 请求头（WECHATPAY2-SHA256-RSA2048 格式）

        格式：
            WECHATPAY2-SHA256-RSA2048 mchid="...",serial_no="...",nonce_str="...",timestamp="...",signature="..."

        Args:
            method: HTTP 方法
            url: 请求 URL
            body: 请求体
        Returns:
            Authorization 头完整字符串
        """
        signature, timestamp, nonce = self.generate_request_signature(method, url, body)
        auth = (
            f"WECHATPAY2-SHA256-RSA2048 "
            f'mchid="{self.mch_id}",'
            f'nonce_str="{nonce}",'
            f'timestamp="{timestamp}",'
            f'serial_no="{self.serial_no}",'
            f'signature="{signature}"'
        )
        return auth
