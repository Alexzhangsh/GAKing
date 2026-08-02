# @ai-generated
"""
用户佣金账户 DAO
继承 BaseDAO；余额变动用 SELECT...FOR UPDATE 悲观锁 + 事务；commit 后失效账户缓存
仅数据存取 + 缓存失效，不含业务计算（手续费计算在 Service 层）

B08 补全项（2026-08-02，与 B07 解耦）：
1. 覆写 logic_delete_by_id / batch_logic_delete / list_all / paginate_list：commit 后失效缓存
2. batch_get_for_update：批量行锁多个用户账户（并发提现批量审核等场景）
3. adjust_balance_batch：批量账户余额变动（内部逐单锁 + 校验，单条失败不阻断整体）
4. list_accounts_by_balance_ge：按可用余额下限筛选账户（后台资产看板）
"""
import json
import logging
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.redis_client import RedisClient
from src.config.constants import (
    CacheTTL,
    CACHE_KEY_USER_ACCOUNT,
)
from src.dao.base_dao import BaseDAO
from src.models.business.user_commission_account_model import UserCommissionAccount

logger = logging.getLogger("dao.user_commission_account")


class UserCommissionAccountDAO(BaseDAO):
    """用户佣金账户 DAO"""

    model_class = UserCommissionAccount

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    # ── 基础查询 ────────────────────────────────────────

    async def get_by_user_id(self, user_id: int) -> Optional[UserCommissionAccount]:
        """按 user_id 查询账户（自动过滤软删除）

        Args:
            user_id: 平台用户ID
        Returns:
            账户实例 或 None
        """
        stmt = self._active_query().where(UserCommissionAccount.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_update(self, user_id: int) -> Optional[UserCommissionAccount]:
        """SELECT ... FOR UPDATE 行级悲观锁（必须在事务内调用）

        用于余额变动前锁定账户行，防止并发更新导致超扣。
        绕过缓存直接查库，确保拿到最新余额。
        """
        stmt = (
            select(UserCommissionAccount)
            .where(
                and_(
                    UserCommissionAccount.user_id == user_id,
                    UserCommissionAccount.is_delete == False,  # noqa: E712
                )
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_by_user_id(self, user_id: int) -> UserCommissionAccount:
        """获取或创建用户账户（不存在则新建，初始余额全 0）

        Args:
            user_id: 平台用户ID
        Returns:
            账户实例（已 commit）
        """
        account = await self.get_by_user_id(user_id)
        if account is not None:
            return account

        account = UserCommissionAccount(
            user_id=user_id,
            total_balance=Decimal("0.00"),
            available_balance=Decimal("0.00"),
            frozen_balance=Decimal("0.00"),
            cumulative_withdrawn=Decimal("0.00"),
            cumulative_fee=Decimal("0.00"),
            last_settle_date=None,
            version=0,
        )
        self.session.add(account)
        try:
            await self.session.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.warning(
                "get_or_create_by_user_id 提交失败已回滚 user_id=%s",
                user_id,
                exc_info=True,
            )
            raise
        logger.info("[dao] 用户佣金账户创建 user_id=%s", user_id)
        return account

    # ── 账户读穿缓存 ──────────────────────────────────

    async def get_account_cached(self, user_id: int) -> Optional[Dict[str, Any]]:
        """按 user_id 查询账户详情，带 Redis 读穿缓存

        缓存策略：
        1. key = gaking:prod:user_account:{user_id}，TTL=10min（CacheTTL.USER_ACCOUNT + ±20% 抖动）
        2. 读穿：未命中查库后回填；命中直接返回序列化 dict
        3. 防穿透：账户不存在时写入 __EMPTY__ 空标记（60s 防同一不存在的 ID 击穿）
        4. 失效：余额变动（adjust_balance/credit_on_reconciliation/update_by_id/create）主动 DEL

        Args:
            user_id: 平台用户ID
        Returns:
            账户详情 dict，账户不存在返回 None
        """
        key = f"{CACHE_KEY_USER_ACCOUNT}{user_id}"

        # 单次 GET 同时识别空标记与正常缓存
        raw = await RedisClient.get(key)
        if raw is not None:
            if raw == "__EMPTY__":
                logger.info("[cache_hit_empty] user_account user_id=%s", user_id)
                return None
            try:
                logger.info("[cache_hit] user_account user_id=%s", user_id)
                return json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(
                    "[cache_corrupt] user_account user_id=%s, 回查库", user_id
                )

        # 未命中：查库并回填
        account = await self.get_by_user_id(user_id)
        if account is None:
            await RedisClient.set_empty_cache(key)  # 60s 空标记防穿透
            logger.info("[cache_miss_empty] user_account user_id=%s", user_id)
            return None

        account_dict = account.to_dict()
        await RedisClient.set_json(key, account_dict, expire=CacheTTL.USER_ACCOUNT)
        logger.info("[cache_miss_set] user_account user_id=%s", user_id)
        return account_dict

    async def _invalidate_account_cache(self, user_id: int) -> None:
        """失效用户账户缓存（余额变动 commit 后调用）"""
        await RedisClient.delete(f"{CACHE_KEY_USER_ACCOUNT}{user_id}")
        logger.info("[cache_invalidate] user_account user_id=%s", user_id)

    # ── 覆写基类写方法：commit 后失效缓存 ──────────────

    async def create(self, data: Dict[str, Any]) -> UserCommissionAccount:
        """覆写基类：账户创建后失效缓存"""
        result = await super().create(data)
        await self._invalidate_account_cache(result.user_id)
        return result

    async def update_by_id(
        self,
        item_id: int,
        data: Dict[str, Any],
    ) -> Optional[UserCommissionAccount]:
        """覆写基类：账户字段更新后失效缓存"""
        result = await super().update_by_id(item_id, data)
        if result is not None:
            await self._invalidate_account_cache(result.user_id)
        return result

    # ── 原子余额调整（4 核心流程共用） ─────────────────

    async def adjust_balance(
        self,
        user_id: int,
        *,
        delta_available: Decimal = Decimal("0"),
        delta_frozen: Decimal = Decimal("0"),
        delta_total: Decimal = Decimal("0"),
        delta_withdrawn: Decimal = Decimal("0"),
        delta_fee: Decimal = Decimal("0"),
    ) -> UserCommissionAccount:
        """原子调整账户余额（事务内 FOR UPDATE + 透支校验 + commit + 失效缓存）

        场景：
        - 发起提现：delta_available=-apply_amount, delta_frozen=+apply_amount
        - 驳回/打款失败：delta_available=+apply_amount, delta_frozen=-apply_amount
        - 打款完成：delta_frozen=-apply_amount, delta_withdrawn=+actual_amount, delta_fee=+fee

        透支校验：available_balance + delta_available >= 0 且 frozen_balance + delta_frozen >= 0
        此为新增方法，不改动 BaseDAO 事务代码。

        Args:
            user_id: 平台用户ID
            delta_available: 可用余额变动量（负为扣减）
            delta_frozen: 冻结余额变动量
            delta_total: 累计佣金变动量
            delta_withdrawn: 累计提现变动量
            delta_fee: 累计手续费变动量
        Returns:
            更新后的账户实例
        Raises:
            ValueError: 账户不存在 / 余额不足（透支）
        """
        account = await self.get_for_update(user_id)
        if account is None:
            raise ValueError(f"用户佣金账户不存在: user_id={user_id}")

        new_available = Decimal(str(account.available_balance)) + delta_available
        new_frozen = Decimal(str(account.frozen_balance)) + delta_frozen

        if new_available < 0:
            raise ValueError(
                f"可用余额不足: user_id={user_id}, 当前可用={account.available_balance}, 扣减={delta_available}"
            )
        if new_frozen < 0:
            raise ValueError(
                f"冻结余额不足: user_id={user_id}, 当前冻结={account.frozen_balance}, 变动={delta_frozen}"
            )

        account.available_balance = new_available
        account.frozen_balance = new_frozen
        account.total_balance = Decimal(str(account.total_balance)) + delta_total
        account.cumulative_withdrawn = (
            Decimal(str(account.cumulative_withdrawn)) + delta_withdrawn
        )
        account.cumulative_fee = Decimal(str(account.cumulative_fee)) + delta_fee
        account.version = (account.version or 0) + 1

        try:
            await self.session.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.warning(
                "adjust_balance 提交失败已回滚 user_id=%s",
                user_id,
                exc_info=True,
            )
            raise

        # commit 成功后失效缓存（顺序：先持久化再失效，避免并发回填脏数据）
        await self._invalidate_account_cache(user_id)
        logger.info(
            "[dao] adjust_balance user_id=%s available=%s frozen=%s withdrawn=%s fee=%s version=%s",
            user_id,
            account.available_balance,
            account.frozen_balance,
            account.cumulative_withdrawn,
            account.cumulative_fee,
            account.version,
        )
        return account

    # ── 对账任务幂等入账 ────────────────────────────────

    async def credit_on_reconciliation(
        self,
        user_id: int,
        amount: Decimal,
        settle_date: date,
    ) -> bool:
        """对账任务入账：将已结算佣金计入可用余额（幂等）

        幂等规则：若 account.last_settle_date >= settle_date，视为当日已入账，跳过返回 False。
        否则：available_balance += amount，total_balance += amount，last_settle_date = settle_date。
        对账任务由分布式锁保护单实例执行，此处不再加 FOR UPDATE。

        Args:
            user_id: 平台用户ID
            amount: 当日已结算佣金总额（Decimal）
            settle_date: 对账目标日期（前一日）
        Returns:
            是否实际入账（True=已入账，False=跳过/幂等/金额<=0）
        """
        if amount <= 0:
            logger.info(
                "[dao] credit_on_reconciliation 跳过(金额<=0) user_id=%s amount=%s",
                user_id,
                amount,
            )
            return False

        account = await self.get_or_create_by_user_id(user_id)

        # 幂等校验：同日或更晚已入账则跳过
        if (
            account.last_settle_date is not None
            and account.last_settle_date >= settle_date
        ):
            logger.info(
                "[dao] credit_on_reconciliation 幂等跳过 user_id=%s last_settle_date=%s settle_date=%s",
                user_id,
                account.last_settle_date,
                settle_date,
            )
            return False

        account.available_balance = Decimal(str(account.available_balance)) + amount
        account.total_balance = Decimal(str(account.total_balance)) + amount
        account.last_settle_date = settle_date
        account.version = (account.version or 0) + 1

        try:
            await self.session.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.warning(
                "credit_on_reconciliation 提交失败已回滚 user_id=%s settle_date=%s",
                user_id,
                settle_date,
                exc_info=True,
            )
            raise

        await self._invalidate_account_cache(user_id)
        logger.info(
            "[dao] credit_on_reconciliation 入账成功 user_id=%s amount=%s settle_date=%s available=%s",
            user_id,
            amount,
            settle_date,
            account.available_balance,
        )
        return True

    # ══════════════════════════════════════════════════════
    # B08 补全：通用 CRUD 覆写（自动失效缓存）
    # ══════════════════════════════════════════════════════

    async def logic_delete_by_id(self, item_id: int) -> bool:
        """覆写基类：账户软删除后失效缓存"""
        # 先拿 user_id（删除后对象 is_delete=True，但 user_id 仍可读取）
        account = await self.get_by_id(item_id)
        if account is None:
            return False
        user_id = account.user_id
        ok = await super().logic_delete_by_id(item_id)
        if ok:
            await self._invalidate_account_cache(user_id)
        return ok

    async def batch_logic_delete(self, item_ids: List[int]) -> int:
        """覆写基类：批量软删除前获取 user_id 列表，commit 后失效缓存

        为避免删除后 user_id 拿不到，先查询再删。
        """
        if not item_ids:
            return 0
        stmt = select(UserCommissionAccount.user_id).where(
            and_(
                UserCommissionAccount.id.in_(item_ids),
                UserCommissionAccount.is_delete == False,  # noqa: E712
            )
        )
        result = await self.session.execute(stmt)
        user_ids: List[int] = [row[0] for row in result.all() if row[0] is not None]
        affected = await super().batch_logic_delete(item_ids)
        for uid in user_ids:
            await self._invalidate_account_cache(uid)
        return affected

    async def list_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
    ) -> List[UserCommissionAccount]:
        """覆写基类：查询后无写操作，无需失效缓存；直接复用基类

        显式覆写以保持「覆写类方法」一致性（与 update/create/delete 系列对齐）。
        """
        return await super().list_all(filters=filters, order_by=order_by)

    async def paginate_list(
        self,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
    ) -> Tuple[List[UserCommissionAccount], int]:
        """覆写基类：分页查询；只读，无需失效缓存"""
        return await super().paginate_list(
            page=page, page_size=page_size, filters=filters, order_by=order_by
        )

    # ══════════════════════════════════════════════════════
    # B08 补全：批量行锁 + 批量余额调整
    # ══════════════════════════════════════════════════════

    async def batch_get_for_update(
        self, user_ids: List[int]
    ) -> List[UserCommissionAccount]:
        """批量 SELECT ... FOR UPDATE 行锁多个用户账户

        场景：批量提现审核时，同时锁定多个用户账户行，防止并发重复扣减。
        注意：参数列表应已去重且按 user_id 有序（避免死锁）。本方法内部会再次
        去重并排序（升序）后执行，符合 MySQL Gap Lock 建议的按主键/索引顺序加锁。

        Args:
            user_ids: 待锁定账户的平台用户 ID 列表
        Returns:
            已锁定的账户实例列表（缺失的用户账户自动跳过，不报错）
        """
        if not user_ids:
            return []
        # 去重 + 升序排序：保证所有并发调用按同一顺序上锁，避免死锁
        unique_ids: List[int] = sorted({int(x) for x in user_ids})
        stmt = (
            select(UserCommissionAccount)
            .where(
                and_(
                    UserCommissionAccount.user_id.in_(unique_ids),
                    UserCommissionAccount.is_delete == False,  # noqa: E712
                )
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def adjust_balance_batch(
        self,
        adjustments: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """批量余额调整（逐单事务独立、单条失败不阻断整体）

        使用场景：后台批量补贴、批量保证金释放等一次操作多用户账户变动。
        每笔调整内部：独立 FOR UPDATE 锁→透支校验→更新→commit→失效缓存；
        单条 try/except，失败记录在 details 中，上层可据此重试。

        Args:
            adjustments: 调整明细列表，每项含 user_id + 5 个 delta（与 adjust_balance 一致）：
                [{"user_id": int,
                  "delta_available": Decimal,
                  "delta_frozen": Decimal (默认 0),
                  "delta_total": Decimal (默认 0),
                  "delta_withdrawn": Decimal (默认 0),
                  "delta_fee": Decimal (默认 0)}, ...]
        Returns:
            与入参等长的结果列表：
                [{"user_id": int, "status": "success"|"failed",
                  "message": str, "new_available": Decimal (成功时)|None}]
        """
        results: List[Dict[str, Any]] = []
        for idx, adj in enumerate(adjustments):
            user_id = int(adj["user_id"])
            delta_available = Decimal(str(adj.get("delta_available", "0")))
            delta_frozen = Decimal(str(adj.get("delta_frozen", "0")))
            delta_total = Decimal(str(adj.get("delta_total", "0")))
            delta_withdrawn = Decimal(str(adj.get("delta_withdrawn", "0")))
            delta_fee = Decimal(str(adj.get("delta_fee", "0")))
            try:
                updated = await self.adjust_balance(
                    user_id,
                    delta_available=delta_available,
                    delta_frozen=delta_frozen,
                    delta_total=delta_total,
                    delta_withdrawn=delta_withdrawn,
                    delta_fee=delta_fee,
                )
                results.append(
                    {
                        "index": idx,
                        "user_id": user_id,
                        "status": "success",
                        "message": "ok",
                        "new_available": Decimal(str(updated.available_balance)),
                    }
                )
            except Exception as e:
                logger.error(
                    "[dao] adjust_balance_batch 单条失败 index=%s user_id=%s error=%s",
                    idx,
                    user_id,
                    e,
                    exc_info=False,
                )
                results.append(
                    {
                        "index": idx,
                        "user_id": user_id,
                        "status": "failed",
                        "message": str(e),
                        "new_available": None,
                    }
                )
        logger.info(
            "[dao] adjust_balance_batch 完成 total=%s success=%s failed=%s",
            len(adjustments),
            sum(1 for r in results if r["status"] == "success"),
            sum(1 for r in results if r["status"] == "failed"),
        )
        return results

    # ══════════════════════════════════════════════════════
    # B08 补全：后台资产看板聚合查询
    # ══════════════════════════════════════════════════════

    async def list_accounts_by_balance_ge(
        self,
        min_available: Decimal,
        page: int = 1,
        page_size: int = 200,
    ) -> Tuple[List[UserCommissionAccount], int]:
        """按可用余额下限筛选账户（后台资产看板：大额可提现用户）

        Args:
            min_available: 可用余额下限（含等值），Decimal，>=0
            page: 页码
            page_size: 每页条数
        Returns:
            (账户列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 200

        stmt = self._active_query().where(
            UserCommissionAccount.available_balance >= min_available
        )
        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(UserCommissionAccount.available_balance.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = list(result.scalars().all())
        return items, total

    async def aggregate_platform_balance(self) -> Dict[str, Decimal]:
        """全平台佣金账户总额聚合（首页资产看板）

        SQL 语义：
            SELECT COALESCE(SUM(total_balance), 0)     AS total,
                   COALESCE(SUM(available_balance), 0) AS available,
                   COALESCE(SUM(frozen_balance), 0)    AS frozen,
                   COALESCE(SUM(cumulative_withdrawn), 0) AS withdrawn,
                   COALESCE(SUM(cumulative_fee), 0)    AS fee
            FROM user_commission_account
            WHERE is_delete = 0

        Returns:
            {"total": Decimal, "available": Decimal, "frozen": Decimal,
             "withdrawn": Decimal, "fee": Decimal, "account_count": int}
        """
        stmt = select(
            func.coalesce(func.sum(UserCommissionAccount.total_balance), 0).label(
                "total"
            ),
            func.coalesce(func.sum(UserCommissionAccount.available_balance), 0).label(
                "available"
            ),
            func.coalesce(func.sum(UserCommissionAccount.frozen_balance), 0).label(
                "frozen"
            ),
            func.coalesce(
                func.sum(UserCommissionAccount.cumulative_withdrawn), 0
            ).label("withdrawn"),
            func.coalesce(func.sum(UserCommissionAccount.cumulative_fee), 0).label(
                "fee"
            ),
            func.count(UserCommissionAccount.id).label("account_count"),
        ).where(
            UserCommissionAccount.is_delete == False  # noqa: E712
        )
        result = await self.session.execute(stmt)
        row = result.one()
        return {
            "total": Decimal(str(row.total)),
            "available": Decimal(str(row.available)),
            "frozen": Decimal(str(row.frozen)),
            "withdrawn": Decimal(str(row.withdrawn)),
            "fee": Decimal(str(row.fee)),
            "account_count": int(row.account_count),
        }
