# @ai-generated
"""创建测试数据：用户、订单、配置"""
import os
import random
import datetime

import pymysql

conn = pymysql.connect(
    host=os.environ.get("DB_HOST", ""),
    port=int(os.environ.get("DB_PORT", "3306")),
    user=os.environ.get("DB_USERNAME", ""),
    password=os.environ.get("DB_PASSWORD", ""),
    database=os.environ.get("DB_DATABASE", ""),
    connect_timeout=5,
)
cursor = conn.cursor()

# 1. 创建测试配置
configs = [
    ("settlement_delay_days", "30", "结算延迟天数"),
    ("admin_jwt_expires_in", "3600", "JWT过期时间(秒)"),
    ("task_order_sync_enable", "true", "订单同步定时任务开关"),
    ("task_reconciliation_enable", "true", "对账定时任务开关"),
]
for key, val, name in configs:
    cursor.execute(
        "INSERT IGNORE INTO gaking_system_config (config_key, config_value, config_name, is_delete, create_time, update_time) VALUES (%s,%s,%s,0,NOW(),NOW())",
        (key, val, name),
    )
print(f"Inserted {len(configs)} configs")

# 2. 获取当前最大user_id
cursor.execute("SELECT MAX(user_id) FROM miniapp_user")
max_user_id = cursor.fetchone()[0] or 0
print(f"Current max user_id: {max_user_id}")

# 3. 创建测试用户
created = 0
for i in range(1, 11):
    openid = f"test_openid_{i}"
    cursor.execute("SELECT user_id FROM miniapp_user WHERE openid=%s", (openid,))
    if not cursor.fetchone():
        new_user_id = max_user_id + i
        cursor.execute(
            "INSERT INTO miniapp_user (user_id, openid, nickname, avatar, status, is_delete, create_time, update_time) VALUES (%s,%s,%s,%s,1,0,NOW(),NOW())",
            (new_user_id, openid, f"测试用户{i}", f"https://img.dftsh.top/avatar/{i}.png"),
        )
        created += 1
print(f"Created {created} new users")

# 4. 获取用户IDs
cursor.execute("SELECT user_id FROM miniapp_user WHERE is_delete=0 ORDER BY user_id")
user_ids = [r[0] for r in cursor.fetchall()]
print(f"Total users: {len(user_ids)}, IDs: {user_ids[:5]}...")

# 5. 创建测试订单（30天内的随机订单）
now = datetime.datetime.now()
created_orders = 0
for i in range(1, 51):
    days_ago = random.randint(0, 29)
    order_time = now - datetime.timedelta(days=days_ago, hours=random.randint(0, 23))
    out_order_no = f"TEST{now.strftime('%Y%m%d')}{i:04d}"
    user_id = random.choice(user_ids)
    pay_amount = round(random.uniform(10, 1000), 2)
    total_commission = round(pay_amount * random.uniform(0.01, 0.15), 2)
    user_commission = round(total_commission * 0.5, 2)
    platform_commission = round(total_commission - user_commission, 2)
    status = random.choice([1, 2, 3])  # 1=pending, 2=confirmed, 3=settled
    channel = random.choice(["myq", "orderx"])

    cursor.execute(
        "SELECT id FROM orders WHERE out_order_no=%s", (out_order_no,)
    )
    if not cursor.fetchone():
        internal_order_no = f"INT{now.strftime('%Y%m%d')}{i:04d}"
        cursor.execute(
            "INSERT INTO orders (user_id, out_order_no, internal_order_no, goods_title, goods_img, pay_amount, total_commission, user_commission, platform_commission, channel_code, order_status, pay_time, transfer_status, is_delete, create_time, update_time) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,NOW(),NOW())",
            (
                user_id,
                out_order_no,
                internal_order_no,
                f"测试商品{i}",
                f"https://img.dftsh.top/goods/{i}.jpg",
                pay_amount,
                total_commission,
                user_commission,
                platform_commission,
                channel,
                status,
                order_time,
                "pending",
            ),
        )
        created_orders += 1

conn.commit()
print(f"Created {created_orders} new orders")

# 验证
cursor.execute("SELECT COUNT(*) FROM orders")
print(f"Total orders: {cursor.fetchone()[0]}")
cursor.execute("SELECT COUNT(*) FROM miniapp_user")
print(f"Total users: {cursor.fetchone()[0]}")
cursor.execute("SELECT COUNT(*) FROM gaking_system_config WHERE is_delete=0")
print(f"Active configs: {cursor.fetchone()[0]}")
cursor.execute("SELECT order_status, COUNT(*) FROM orders GROUP BY order_status")
for row in cursor.fetchall():
    print(f"  Order status {row[0]}: {row[1]}")

conn.close()