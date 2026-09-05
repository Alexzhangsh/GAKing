# @ai-generated
"""
密码哈希工具（B14 新建，不修改 B01-B13 基线）
使用 bcrypt 库直接封装密码哈希与校验（passlib 1.7.4 与 bcrypt 5.x 存在兼容问题，改用 bcrypt 直调）
AdminUser.password 字段为 bcrypt 哈希，禁止明文存储
哈希格式：$2b$12$...（bcrypt cost=12）
"""
import logging

import bcrypt

logger = logging.getLogger("common.b14_password")


class B14PasswordUtil:
    """密码哈希工具（bcrypt 直调封装）

    AdminUser.password 字段统一使用 bcrypt 哈希存储
    bcrypt 限制密码最长 72 字节，超长自动截断
    """

    # bcrypt cost 因子（与 passlib 默认值对齐）
    _COST = 12
    _MAX_BYTES = 72

    @classmethod
    def hash_password(cls, plain: str) -> str:
        """将明文密码哈希为 bcrypt 字符串

        Args:
            plain: 明文密码
        Returns:
            bcrypt 哈希字符串（$2b$12$...）
        """
        if not plain:
            raise ValueError("密码不能为空")
        # bcrypt 限制 72 字节，超长截断（与 passlib 行为一致）
        plain_bytes = plain.encode("utf-8")[: cls._MAX_BYTES]
        salt = bcrypt.gensalt(rounds=cls._COST)
        hashed = bcrypt.hashpw(plain_bytes, salt)
        return hashed.decode("utf-8")

    @classmethod
    def verify_password(cls, plain: str, hashed: str) -> bool:
        """校验明文密码与哈希是否匹配

        Args:
            plain: 明文密码
            hashed: bcrypt 哈希字符串
        Returns:
            True-匹配 False-不匹配
        """
        if not plain or not hashed:
            return False
        try:
            plain_bytes = plain.encode("utf-8")[: cls._MAX_BYTES]
            hashed_bytes = hashed.encode("utf-8")
            return bcrypt.checkpw(plain_bytes, hashed_bytes)
        except Exception as e:
            logger.warning("密码校验异常: %s", e)
            return False

    @classmethod
    def needs_rehash(cls, hashed: str) -> bool:
        """检查哈希是否需要重新哈希（cost 升级时用）

        Args:
            hashed: 现有哈希
        Returns:
            True-需要重新哈希 False-不需要
        """
        try:
            # 解析现有 cost，低于当前 _COST 则需重新哈希
            prefix = hashed.split("$")
            if len(prefix) >= 3 and prefix[1] in ("2a", "2b", "2y"):
                existing_cost = int(prefix[2])
                return existing_cost < cls._COST
            return True
        except Exception:
            return True
