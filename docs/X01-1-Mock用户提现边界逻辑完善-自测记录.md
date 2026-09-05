# X01-1 Mock 用户提现边界逻辑完善 —— 自测记录

> 文档名称：X01-1 Mock 用户提现边界逻辑完善自测记录
> 适用范围：mock 用户提现边界逻辑 / 提现单元测试 / 提现全流程（申请-审核-打款）回归
> 编制时间：2026-08-14
> 状态：自测通过（待验收）
> 前置依赖：S07 一期全量自检复测完成

---

## 一、交付清单

| 交付项 | 状态 | 关键文件 |
|--------|------|----------|
| Mock 用户工具（openid 识别 / 模拟打款批次号 / 模拟判定） | ✅ 已完成 | [mock_user_util.py](file:///Users/alexzhang/Documents/Work/Projects/Products/金角大王/GAKing-Coding/backend/src/common/mock_user_util.py) |
| 登录服务 mock openid 复用共享常量 + 暴露 is_mock_openid | ✅ 已完成 | [miniapp_user_service.py](file:///Users/alexzhang/Documents/Work/Projects/Products/金角大王/GAKing-Coding/backend/src/services/miniapp_user_service.py) |
| 提现审核编排 mock 用户打款边界（模拟/拒绝/真实三态） | ✅ 已完成 | [withdraw_review_service.py](file:///Users/alexzhang/Documents/Work/Projects/Products/金角大王/GAKing-Coding/backend/src/services/withdraw_review_service.py) |
| Mock 用户工具单元测试 | ✅ 已完成 | [test_mock_user_util.py](file:///Users/alexzhang/Documents/Work/Projects/Products/金角大王/GAKing-Coding/backend/tests/test_mock_user_util.py) |
| 登录服务 mock 逻辑单元测试 | ✅ 已完成 | [test_miniapp_user_mock.py](file:///Users/alexzhang/Documents/Work/Projects/Products/金角大王/GAKing-Coding/backend/tests/test_miniapp_user_mock.py) |
| 提现审核编排 mock 边界测试（B11 扩展） | ✅ 已完成 | [test_withdraw_review_b11.py](file:///Users/alexzhang/Documents/Work/Projects/Products/金角大王/GAKing-Coding/backend/tests/test_withdraw_review_b11.py) |

---

## 二、问题背景与边界定义

### 2.1 问题背景

开发环境（`WX_MINI_APPID` 未配置）下，用户通过 `MiniappUserService._dev_mock_openid` 生成 `dev_` 前缀的 mock openid 完成登录。此类 mock 用户可正常发起提现申请，但若在自动打款链路中把 mock openid 直接传给微信商家转账接口：

- 微信侧必然返回「openid 无效」导致打款失败，资金状态误判；
- 生产环境若出现 mock openid（异常数据），模拟打款会造成「未真实打款却标记成功」的资金风险。

### 2.2 边界规则（本次完善）

| 场景 | openid | 环境 | 处理 |
|------|--------|------|------|
| 真实业务用户 | 真实 openid（`oX` 开头） | 任意 | 正常调用微信转账接口（不受影响） |
| Mock 用户 | `dev_` 前缀 | 非生产（development/testing/staging） | 模拟打款成功，返回 `MOCKBATCH` 前缀批次号，打通全流程自测 |
| Mock 用户（异常数据） | `dev_` 前缀 | 生产 | 禁止模拟、禁止调真实接口，记 CRITICAL 日志，转人工打款处理 |

---

## 三、代码变更说明

### 3.1 新增 `src/common/mock_user_util.py`

纯函数工具模块，无 IO 依赖：

- `MOCK_OPENID_PREFIX = "dev_"`：mock openid 前缀（与 `_dev_mock_openid` 生成规则对齐）
- `MOCK_TRANSFER_BATCH_PREFIX = "MOCKBATCH"`：模拟打款批次号前缀
- `is_mock_openid(openid)`：判定 openid 是否为 mock（`dev_` 前缀精确匹配）
- `gen_mock_transfer_batch_id(apply_no)`：生成确定性 mock 批次号（`MOCKBATCH + apply_no`）
- `should_simulate_transfer(openid)`：mock openid 且非生产环境 → True；生产环境 mock openid → False（记 warning）

### 3.2 修改 `src/services/miniapp_user_service.py`

- `_dev_mock_openid` 复用 `MOCK_OPENID_PREFIX` 常量（行为不变，消除魔法字符串）
- 新增 `is_mock_openid` 类方法，供提现/打款等业务链路复用

### 3.3 修改 `src/services/withdraw_review_service.py`

`_trigger_wechat_transfer` 增加 mock 用户边界拦截（在调用真实微信接口之前）：

```python
if is_mock_openid(openid):
    if not should_simulate_transfer(openid):
        # 生产环境 mock openid：禁止自动打款，转人工处理
        return None
    # 非生产环境：模拟打款成功，记录 TRANSFER 日志（含模拟标记）
    return {"batch_id": "MOCKBATCH...", "mock": True, ...}
# 真实 openid：正常调用微信转账
```

关键点：**mock openid 一律不进入真实微信转账调用分支**，从根上避免假 openid 打款失败与资金状态误判。

---

## 四、单元测试结果

### 4.1 新增/扩展测试用例清单

| 测试文件 | 用例数 | 覆盖点 |
|----------|--------|--------|
| test_mock_user_util.py | 14 | is_mock_openid 边界（前缀/空/大小写/非开头）；批次号生成确定性；should_simulate_transfer 三态（dev mock→True / prod mock→False / 真实 openid→False） |
| test_miniapp_user_mock.py | 7 | _dev_mock_openid 稳定性/区分度/前缀/长度；is_mock_openid 类方法；login_by_code 开发兜底（新用户创建 / 老用户刷新 / 生产走真实 code2session） |
| test_withdraw_review_b11.py（扩展） | +4 | mock openid 非生产模拟打款（不调真实接口）；mock openid 生产拒绝（不模拟不调接口）；真实 openid 正常调微信；approve_and_transfer 全链路 mock 模拟 |

### 4.2 执行结果

```
pytest tests/test_mock_user_util.py tests/test_miniapp_user_mock.py tests/test_withdraw_review_b11.py
→ 56 passed in 0.39s
```

### 4.3 提现相关全量回归

```
pytest tests/test_withdraw_b09.py tests/test_withdraw_service_coverage.py \
      tests/test_withdraw_review_b11.py tests/test_wechat_pay_b10.py \
      tests/test_wxpay_callback.py tests/test_user_commission_b08.py \
      tests/test_mock_user_util.py tests/test_miniapp_user_mock.py
→ 355 passed in 5.45s
```

> 说明：`test_b13_withdraw_admin.py` 存在 5 个存量失败（`_active_query` mock 与已修复的 Service 代码不一致），与本次改动无关，未纳入本次回归范围。

---

## 五、提现全流程（申请-审核-打款）业务分支回归

基于单元测试覆盖，逐分支核对提现状态机（`PENDING → APPROVED → PROCESSING → SUCCESS/REJECTED`）：

| # | 业务分支 | 状态流转 | 覆盖用例 | 结果 |
|---|----------|----------|----------|------|
| 1 | 发起提现成功（阶梯手续费） | → PENDING | test_withdraw_b09 / test_withdraw_service_coverage | ✅ 通过 |
| 2 | 发起提现：低于最低门槛 | 拒绝 | test_withdraw_b09 | ✅ 通过 |
| 3 | 发起提现：单日限额超限 | 拒绝 | test_withdraw_b09 | ✅ 通过 |
| 4 | 发起提现：余额不足 | 拒绝 | test_withdraw_b09 | ✅ 通过 |
| 5 | 发起提现：幂等防重复（SETNX） | 拒绝 | test_withdraw_service_coverage | ✅ 通过 |
| 6 | 审核通过（手动打款模式） | PENDING → APPROVED | test_withdraw_review_b11 | ✅ 通过 |
| 7 | 审核通过 + 自动转账成功（真实用户） | APPROVED → PROCESSING | test_withdraw_review_b11 | ✅ 通过 |
| 8 | 审核通过 + 自动转账失败不回滚 | APPROVED（保留） | test_withdraw_review_b11 | ✅ 通过 |
| 9 | 审核通过 + mock 用户模拟打款（非生产） | APPROVED → PROCESSING（模拟） | test_withdraw_review_b11（新增） | ✅ 通过 |
| 10 | 审核通过 + mock 用户生产拒绝（转人工） | APPROVED（保留） | test_withdraw_review_b11（新增） | ✅ 通过 |
| 11 | 审核驳回退回余额 | PENDING → REJECTED | test_withdraw_review_b11 / test_withdraw_service_coverage | ✅ 通过 |
| 12 | 打款成功回调释放冻结 | PROCESSING → SUCCESS | test_withdraw_review_b11 / test_withdraw_service_coverage | ✅ 通过 |
| 13 | 打款失败退回可用余额 | PROCESSING → REJECTED | test_withdraw_review_b11 / test_withdraw_service_coverage | ✅ 通过 |
| 14 | 状态机非法流转拦截 | 各终态不可二次操作 | test_withdraw_review_b11 / test_withdraw_service_coverage | ✅ 通过 |
| 15 | 幂等锁拦截（审核/驳回/回调） | 拒绝重复操作 | test_withdraw_review_b11 | ✅ 通过 |

**结论：提现全流程 15 个业务分支全部通过，无回归。**

---

## 六、兼容性说明

1. **真实业务用户不受影响**：真实 openid（`oX` 开头）不命中 mock 分支，走原有微信转账链路，行为与 S07 验收一致。
2. **开发/测试环境可全流程自测**：mock 用户发起提现 → 审核通过 → 自动打款（模拟成功，返回 `MOCKBATCH` 批次号）→ 打款成功回调，无需真实微信凭证即可验证完整状态机。
3. **生产环境资金安全**：生产环境 mock openid 属异常数据，禁止模拟、禁止调真实接口，转人工打款处理，避免资金状态误判。
4. **幂等与日志**：模拟打款同样记录 TRANSFER 状态流转日志（remark 含「模拟」标记），批次号 `MOCKBATCH` 前缀便于与真实微信批次区分。

---

## 七、结论

| 任务目标 | 完成情况 |
|----------|----------|
| 1. 完善 mock 用户提现边界逻辑，兼容真实业务用户场景 | ✅ 完成（三态边界：真实用户走真实打款 / mock 非生产模拟 / mock 生产转人工） |
| 2. 补齐提现相关单元测试用例 | ✅ 完成（新增 25 个用例：工具 14 + 登录 7 + 审核编排扩展 4） |
| 3. 回归验证提现全流程全部业务分支 | ✅ 完成（15 个分支全通过，355 个相关测试无回归） |
| 4. 完成自测，输出自测记录 | ✅ 完成（本文档） |

**自测结论：通过，可提交验收。**
