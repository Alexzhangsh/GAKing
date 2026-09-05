# @ai-generated
"""
微信支付V3转账业务服务层（B10 新建）

职责：
1. 单笔转账到零钱（发起新批次，含1条明细）
2. 批量转账（发起新批次，含N条明细）
3. 转账结果查询（按批次ID查 / 按明细ID查）
4. 转账回调通知解析（验签 + 解密 + 状态映射）
5. 幂等防重复打款（Redis SETNX 转账单号，7天过期）

设计要点：
1. 配置从 gaking_pay_config 动态读取（PayConfigUtil 已有，不重复封装）
2. 转账单号 out_batch_no 由调用方传入（对应提现申请 apply_no），本服务负责幂等
3. 回调解析返回标准化的转账结果 dict，供 withdraw_service 更新状态
4. 全部异步，不阻塞；异常统一抛 WechatPayError（继承 BizException）

约束：不修改 B01-B09 基线代码
"""
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.common.pay_config_util import PayConfigUtil
from src.common.redis_client import RedisClient
from src.common.wechat_pay.client import WechatPayClient
from src.common.wechat_pay.constants import (
    CACHE_KEY_TRANSFER_IDEMPOTENT,
    CACHE_TTL_TRANSFER_IDEMPOTENT,
    WECHAT_PAY_API_QUERY_BATCH,
    WECHAT_PAY_API_QUERY_DETAIL,
    WECHAT_PAY_API_TRANSFER_BATCH,
    WECHAT_TRANSFER_STATUS_MAP,
)
from src.common.wechat_pay.exceptions import (
    WECHAT_PAY_ERROR_CALLBACK_VERIFY,
    WECHAT_PAY_ERROR_DUPLICATE,
    WECHAT_PAY_ERROR_PARAM,
    WECHAT_PAY_ERROR_PARSE,
    WechatPayError,
)
from src.common.wechat_pay.signer import WechatPaySigner
from src.config.constants import REDIS_PREFIX
from src.models.system.pay_config import PayConfig
from src.db.init_db import DatabaseManager
from sqlalchemy import select

logger = logging.getLogger("common.wechat_pay.service")


class WechatPayTransferService:
    """微信支付V3转账服务

    封装单笔/批量转账、查询、回调解析、幂等控制
    依赖 WechatPayClient（HTTP+签名+熔断）+ RedisClient（幂等）+ PayConfig（商户配置）
    """

    def __init__(self, client: WechatPayClient) -> None:
        """初始化转账服务

        Args:
            client: 微信支付 HTTP 客户端（含签名器 + 熔断器）
        """
        self.client = client
        self.signer = client.signer

    # ══════════════════════════════════════════════════════
    # 1. 单笔转账
    # ══════════════════════════════════════════════════════

    async def transfer_single(
        self,
        out_batch_no: str,
        out_detail_no: str,
        transfer_amount: Decimal,
        openid: str,
        transfer_remark: str,
        *,
        transfer_scene_id: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """单笔转账到零钱（批次含1条明细）

        幂等：out_batch_no 作为幂等键，重复请求直接返回已有结果

        Args:
            out_batch_no: 商户批次单号（对应提现申请 apply_no，全局唯一）
            out_detail_no: 商户明细单号（对应单笔转账唯一标识）
            transfer_amount: 转账金额（元，Decimal，精度2位）
            openid: 收款用户 openid
            transfer_remark: 转账备注（用户可见，如"佣金提现"）
            transfer_scene_id: 转账场景ID（None 从配置读取）
            user_name: 收款用户姓名（明文，需 RSA 加密；None 不传）
        Returns:
            {"batch_id": "微信批次ID", "out_batch_no": "...", "create_time": "..."}
        Raises:
            WechatPayError: 幂等重复 / 参数错误 / API失败
        """
        # 金额转分（微信支付V3要求单位为分）
        amount_in_fen = self._yuan_to_fen(transfer_amount)

        # 构造明细
        detail = {
            "out_detail_no": out_detail_no,
            "transfer_amount": amount_in_fen,
            "transfer_remark": transfer_remark,
            "openid": openid,
        }
        if user_name:
            detail["user_name"] = user_name  # 实际需加密，此处占位

        # 构造批次请求体
        body: Dict[str, Any] = {
            "out_batch_no": out_batch_no,
            "batch_name": "佣金提现",
            "batch_remark": "GAKing佣金提现",
            "total_amount": amount_in_fen,
            "total_num": 1,
            "transfer_detail_list": [detail],
        }
        if transfer_scene_id:
            body["transfer_scene_id"] = transfer_scene_id

        return await self._do_transfer_with_idempotent(out_batch_no, body)

    # ══════════════════════════════════════════════════════
    # 2. 批量转账
    # ══════════════════════════════════════════════════════

    async def transfer_batch(
        self,
        out_batch_no: str,
        batch_name: str,
        details: List[Dict[str, Any]],
        *,
        transfer_scene_id: Optional[str] = None,
        batch_remark: str = "GAKing批量佣金提现",
    ) -> Dict[str, Any]:
        """批量转账到零钱（批次含N条明细）

        Args:
            out_batch_no: 商户批次单号（幂等键）
            batch_name: 批次名称
            details: 明细列表 [{"out_detail_no", "transfer_amount(Decimal)", "openid", "transfer_remark", "user_name?"}]
            transfer_scene_id: 转账场景ID
            batch_remark: 批次备注
        Returns:
            {"batch_id": "...", "out_batch_no": "...", "create_time": "..."}
        Raises:
            WechatPayError: 幂等重复 / 参数错误 / API失败
        """
        if not details:
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_PARAM,
                msg="批量转账明细列表不能为空",
            )
        if len(details) > 1000:
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_PARAM,
                msg="单批次转账明细不能超过1000条",
            )

        # 构造明细列表 + 汇总金额/笔数
        detail_list = []
        total_amount_fen = 0
        for d in details:
            amount = Decimal(str(d["transfer_amount"]))
            amount_fen = self._yuan_to_fen(amount)
            total_amount_fen += amount_fen
            item: Dict[str, Any] = {
                "out_detail_no": d["out_detail_no"],
                "transfer_amount": amount_fen,
                "transfer_remark": d.get("transfer_remark", "佣金提现"),
                "openid": d["openid"],
            }
            if d.get("user_name"):
                item["user_name"] = d["user_name"]
            detail_list.append(item)

        body: Dict[str, Any] = {
            "out_batch_no": out_batch_no,
            "batch_name": batch_name,
            "batch_remark": batch_remark,
            "total_amount": total_amount_fen,
            "total_num": len(detail_list),
            "transfer_detail_list": detail_list,
        }
        if transfer_scene_id:
            body["transfer_scene_id"] = transfer_scene_id

        return await self._do_transfer_with_idempotent(out_batch_no, body)

    # ══════════════════════════════════════════════════════
    # 3. 转账结果查询
    # ══════════════════════════════════════════════════════

    async def query_batch(
        self, batch_id: str, *, need_query_detail: bool = False
    ) -> Dict[str, Any]:
        """查询批次转账结果

        Args:
            batch_id: 微信批次ID（transfer_single/transfer_batch 返回的 batch_id）
            need_query_detail: 是否查询明细列表
        Returns:
            {"batch_id", "batch_status", "total_amount", "total_num", ...}
        Raises:
            WechatPayError: API失败
        """
        path = WECHAT_PAY_API_QUERY_BATCH.format(batch_id=batch_id)
        if need_query_detail:
            path += "?need_query_detail=true"
        result = await self.client.get(path)
        logger.info(
            "[wechat_pay_service] 查询批次 batch_id=%s status=%s",
            batch_id,
            result.get("batch_status"),
        )
        return result

    async def query_detail(self, batch_id: str, detail_id: str) -> Dict[str, Any]:
        """查询单笔转账明细结果

        Args:
            batch_id: 微信批次ID
            detail_id: 微信明细ID（或商户明细单号 out_detail_no）
        Returns:
            {"detail_id", "detail_status", "transfer_amount", ...}
        Raises:
            WechatPayError: API失败
        """
        path = WECHAT_PAY_API_QUERY_DETAIL.format(
            batch_id=batch_id, detail_id=detail_id
        )
        result = await self.client.get(path)
        logger.info(
            "[wechat_pay_service] 查询明细 batch_id=%s detail_id=%s status=%s",
            batch_id,
            detail_id,
            result.get("detail_status"),
        )
        return result

    # ══════════════════════════════════════════════════════
    # 4. 回调通知解析
    # ══════════════════════════════════════════════════════

    async def parse_callback(
        self,
        timestamp: str,
        nonce: str,
        body: str,
        signature: str,
        platform_cert_pem: str,
        api_v3_key: str,
    ) -> Dict[str, Any]:
        """解析微信转账回调通知

        流程：验签 → 解密密文 → 映射状态 → 返回标准化结果

        Args:
            timestamp: 回调头 Wechatpay-Timestamp
            nonce: 回调头 Wechatpay-Nonce
            body: 回调请求体原文
            signature: 回调头 Wechatpay-Signature
            platform_cert_pem: 微信平台证书 PEM（用于验签）
            api_v3_key: APIv3 密钥（用于解密）
        Returns:
            标准化结果 dict：
            {"out_batch_no", "batch_id", "transfer_status", "raw": {...}}
        Raises:
            WechatPayError: 验签失败 / 解密失败
        """
        # 1. 验签
        ok = WechatPaySigner.verify_callback_signature(
            platform_cert_pem=platform_cert_pem,
            timestamp=timestamp,
            nonce=nonce,
            body=body,
            signature=signature,
        )
        if not ok:
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_CALLBACK_VERIFY,
                msg="微信回调验签失败",
            )

        # 2. 解析通知体外层
        try:
            notification = json.loads(body)
        except json.JSONDecodeError as e:
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_PARSE,
                msg=f"回调通知体JSON解析失败: {e}",
            )

        resource = notification.get("resource", {})
        if not resource:
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_PARSE,
                msg="回调通知缺少 resource 字段",
            )

        # 3. 解密密文
        plaintext = WechatPaySigner.decrypt_callback_resource(
            api_v3_key=api_v3_key,
            associated_data=resource.get("associated_data", ""),
            nonce=resource.get("nonce", ""),
            ciphertext=resource.get("ciphertext", ""),
        )

        # 4. 解析解密后的 JSON
        try:
            decrypt_data = json.loads(plaintext)
        except json.JSONDecodeError as e:
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_PARSE,
                msg=f"解密后JSON解析失败: {e}",
            )

        # 5. 映射状态
        wechat_status = decrypt_data.get("batch_status") or decrypt_data.get(
            "detail_status", ""
        )
        unified_status = WECHAT_TRANSFER_STATUS_MAP.get(wechat_status, "UNKNOWN")

        result = {
            "out_batch_no": decrypt_data.get("out_batch_no", ""),
            "batch_id": decrypt_data.get("batch_id", ""),
            "out_detail_no": decrypt_data.get("out_detail_no", ""),
            "detail_id": decrypt_data.get("detail_id", ""),
            "transfer_status": unified_status,
            "wechat_status": wechat_status,
            "fail_reason": decrypt_data.get("fail_reason", ""),
            "raw": decrypt_data,
        }
        logger.info(
            "[wechat_pay_service] 回调解析成功 out_batch_no=%s status=%s",
            result["out_batch_no"],
            result["transfer_status"],
        )
        return result

    # ══════════════════════════════════════════════════════
    # 5. 幂等控制（内部方法）
    # ══════════════════════════════════════════════════════

    async def _do_transfer_with_idempotent(
        self,
        out_batch_no: str,
        body: Dict[str, Any],
    ) -> Dict[str, Any]:
        """带幂等控制的转账请求

        1. SETNX 幂等键，已存在 → 查 Redis 返回已有结果
        2. 调用微信 API
        3. 成功 → 回写 Redis（batch_id + 时间戳）
        4. 失败 → 删除幂等键（允许重试）

        Args:
            out_batch_no: 商户批次单号（幂等键）
            body: 请求体
        Returns:
            转账结果 dict
        """
        idem_key = f"{CACHE_KEY_TRANSFER_IDEMPOTENT}{out_batch_no}"

        # 1. 幂等检查（SETNX）
        acquired = await RedisClient.setnx(idem_key, json.dumps({"status": "PENDING"}))
        if not acquired:
            # 已有记录，返回已存在的结果
            cached = await RedisClient.get(idem_key)
            if cached:
                try:
                    cached_data = json.loads(cached)
                    if cached_data.get("batch_id"):
                        logger.info(
                            "[wechat_pay_service] 幂等命中 out_batch_no=%s "
                            "batch_id=%s",
                            out_batch_no,
                            cached_data["batch_id"],
                        )
                        return cached_data
                except json.JSONDecodeError:
                    pass
            # 幂等键存在但无有效结果（可能在处理中）→ 拒绝重复
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_DUPLICATE,
                msg=f"转账单号 {out_batch_no} 已存在或正在处理中，请勿重复提交",
            )

        # 2. 设置 TTL（7天，覆盖对账周期）
        await RedisClient.expire(idem_key, CACHE_TTL_TRANSFER_IDEMPOTENT)

        # 3. 调用微信 API
        try:
            result = await self.client.post(WECHAT_PAY_API_TRANSFER_BATCH, body)
            # 4. 成功 → 回写 Redis
            success_data = {
                "batch_id": result.get("batch_id", ""),
                "out_batch_no": out_batch_no,
                "create_time": result.get("create_time", ""),
                "status": "ACCEPTED",
                "created_at": datetime.now().isoformat(),
            }
            await RedisClient.set(
                idem_key,
                json.dumps(success_data, ensure_ascii=False),
                expire=CACHE_TTL_TRANSFER_IDEMPOTENT,
            )
            logger.info(
                "[wechat_pay_service] 转账成功 out_batch_no=%s batch_id=%s",
                out_batch_no,
                success_data["batch_id"],
            )
            return success_data

        except Exception:
            # 5. 失败 → 删除幂等键，允许重试
            await RedisClient.delete(idem_key)
            logger.warning(
                "[wechat_pay_service] 转账失败，已清除幂等键 out_batch_no=%s",
                out_batch_no,
            )
            raise

    # ══════════════════════════════════════════════════════
    # 工具方法
    # ══════════════════════════════════════════════════════

    @staticmethod
    def _yuan_to_fen(amount: Decimal) -> int:
        """元转分（微信支付V3金额单位为分）

        Args:
            amount: 金额（元，Decimal）
        Returns:
            金额（分，int）
        Raises:
            WechatPayError: 金额非法
        """
        try:
            amount = Decimal(str(amount))
            if amount <= 0:
                raise WechatPayError(
                    code=WECHAT_PAY_ERROR_PARAM,
                    msg=f"转账金额必须大于0，当前: {amount}",
                )
            fen = int((amount * 100).to_integral_value())
            return fen
        except WechatPayError:
            raise
        except Exception as e:
            raise WechatPayError(
                code=WECHAT_PAY_ERROR_PARAM,
                msg=f"转账金额转换失败: {e}",
            )


# ══════════════════════════════════════════════════════
# 工厂方法：从 PayConfig 创建服务实例
# ══════════════════════════════════════════════════════


async def create_wechat_pay_service() -> WechatPayTransferService:
    """从 gaking_pay_config 创建微信支付转账服务实例

    读取启用的 PayConfig 行，构造 signer + client + service
    Returns:
        WechatPayTransferService 实例
    Raises:
        WechatPayError: 配置不存在 / 证书加载失败
    """
    try:
        async with DatabaseManager.get_session() as session:
            stmt = (
                select(PayConfig)
                .where(
                    PayConfig.status == True, PayConfig.is_delete == False
                )  # noqa: E712
                .order_by(PayConfig.id.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            config: Optional[PayConfig] = result.scalar_one_or_none()

            if config is None:
                raise WechatPayError(
                    code=WECHAT_PAY_ERROR_PARAM,
                    msg="gaking_pay_config 无启用配置行，无法初始化微信支付服务",
                )

            signer = WechatPaySigner(
                mch_id=config.mch_id,
                serial_no=config.serial_no,
                private_key_path=config.private_key_path,
            )
            client = WechatPayClient(signer)
            service = WechatPayTransferService(client)
            logger.info(
                "[wechat_pay_service] 服务实例创建成功 mch_id=%s",
                config.mch_id,
            )
            return service
    except WechatPayError:
        raise
    except Exception as e:
        logger.error("[wechat_pay_service] 创建服务实例失败: %s", e, exc_info=True)
        raise WechatPayError(
            code=WECHAT_PAY_ERROR_PARAM,
            msg=f"创建微信支付服务实例失败: {e}",
        )
