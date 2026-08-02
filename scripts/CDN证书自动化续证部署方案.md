# @ai-generated
# ================================================================
# 华为云CDN img.dftsh.top 自有证书全自动化续证部署方案
# ================================================================

## 一、背景与问题

### 1.1 现状
- **服务器Nginx证书**：✅ certbot自动续证正常，每90天自动续期
- **华为云CDN证书**：❌ 静态粘贴自有证书（certificate_type: 0），无自动更新机制
- **现有脚本**：仅同步到SCM托管证书，无CDN自有证书更新逻辑

### 1.2 风险
- CDN节点上的证书90天后过期，用户访问 img.dftsh.top 将出现证书错误
- 图片资源加载失败，影响业务正常运行

---

## 二、方案架构

### 2.1 整体流程
```
certbot renew (每月3日)
    ↓
Nginx reload (已有)
    ↓
SCM证书同步 (已有)
    ↓
[新增] CDN自有证书同步 (本方案)
    ├─ 读取 /etc/letsencrypt/live/wild_dftsh/ 最新证书
    ├─ 调用华为云CDN UpdateDomainMultiCertificates API
    ├─ 3次重试 + 日志记录 + 异常告警
    └─ 证书有效期验证
```

### 2.2 交付物清单

| 文件 | 路径 | 用途 |
|-----|------|------|
| sync_huawei_cdn_cert.sh | /usr/local/bin/ | CDN证书同步主脚本 |
| check_cdn_cert_validity.sh | /usr/local/bin/ | 证书有效期验证工具 |
| send_cert_alert.sh | /usr/local/bin/ | 告警发送工具 |
| cdn_cert_alert_config | /etc/ | 告警配置文件 |

---

## 三、部署步骤

### 3.1 前置条件检查

```bash
# 1. 确认华为云CLI已安装
which hcloud
hcloud --version

# 2. 确认环境变量文件存在
ls -la /etc/huawei_cloud_env
cat /etc/huawei_cloud_env | grep -E "^HUAWEI_" | head -5

# 3. 确认本地证书存在
ls -la /etc/letsencrypt/live/wild_dftsh/

# 4. 确认openssl可用
openssl version
```

### 3.2 权限要求

AK/SK需要具备以下CDN权限：
- `cdn:domain:query` - 查询域名配置
- `cdn:domain:modifyHttps` - 修改HTTPS配置

**验证方法：**
```bash
# 先加载环境变量
. /etc/huawei_cloud_env

# 配置hcloud
hcloud configure set \
  --region=cn-east-3 \
  --domain-id="$HUAWEI_DOMAIN_ID" \
  --access-key="$HUAWEI_AK" \
  --secret-key="$HUAWEI_SK"

# 测试查询CDN配置
hcloud CDN ShowCertificatesHttpsInfo/v2 --domain_name=img.dftsh.top
```

### 3.3 部署脚本

```bash
# 1. 上传脚本到服务器 (在本地项目目录执行)
scp scripts/sync_huawei_cdn_cert.sh root@<server-ip>:/usr/local/bin/
scp scripts/check_cdn_cert_validity.sh root@<server-ip>:/usr/local/bin/
scp scripts/send_cert_alert.sh root@<server-ip>:/usr/local/bin/
scp scripts/cdn_cert_alert_config.template root@<server-ip>:/etc/cdn_cert_alert_config

# 2. 添加执行权限
chmod +x /usr/local/bin/sync_huawei_cdn_cert.sh
chmod +x /usr/local/bin/check_cdn_cert_validity.sh
chmod +x /usr/local/bin/send_cert_alert.sh

# 3. 配置告警 (可选)
vi /etc/cdn_cert_alert_config
# 填写 WECOM_WEBHOOK 或 DINGTALK_WEBHOOK
```

### 3.4 修改crontab定时任务

**原有任务（保留）：**
```bash
2 0 3 * * certbot renew --cert-name wild_dftsh --quiet ; /usr/local/bin/reload_nginx_and_sync_huawei_dftsh_cert.sh >> /var/log/certbot-dftsh-renew.log 2>&1
```

**修改后（追加CDN同步）：**
```bash
2 0 3 * * certbot renew --cert-name wild_dftsh --quiet ; /usr/local/bin/reload_nginx_and_sync_huawei_dftsh_cert.sh >> /var/log/certbot-dftsh-renew.log 2>&1 ; /usr/local/bin/sync_huawei_cdn_cert.sh >> /var/log/certbot-cdn-sync.log 2>&1
```

**操作命令：**
```bash
# 查看当前crontab
crontab -l

# 编辑crontab
crontab -e

# 验证修改
crontab -l | grep certbot
```

### 3.5 配置每周巡检（可选）

```bash
# 添加每周一上午10点检查证书有效期
0 10 * * 1 /usr/local/bin/check_cdn_cert_validity.sh >> /var/log/cdn-cert-check.log 2>&1
```

---

## 四、手动测试步骤

### 4.1 测试前准备

```bash
# 1. 记录当前CDN证书到期时间
echo | openssl s_client -connect img.dftsh.top:443 -servername img.dftsh.top 2>/dev/null | openssl x509 -noout -dates

# 2. 记录本地证书到期时间
openssl x509 -in /etc/letsencrypt/live/wild_dftsh/cert.pem -noout -dates
```

### 4.2 执行同步测试

```bash
# 手动运行同步脚本
bash /usr/local/bin/sync_huawei_cdn_cert.sh

# 实时查看日志
tail -f /var/log/certbot-cdn-sync.log
```

### 4.3 验证更新结果

**重要：CDN节点更新有延迟，通常5-15分钟，请耐心等待**

```bash
# 等待5分钟后检查
sleep 300

# 方法1：使用验证脚本
bash /usr/local/bin/check_cdn_cert_validity.sh

# 方法2：手动检查CDN节点证书
echo | openssl s_client -connect img.dftsh.top:443 -servername img.dftsh.top 2>/dev/null | openssl x509 -noout -dates

# 方法3：查询华为云CDN配置
hcloud CDN ShowCertificatesHttpsInfo/v2 --domain_name=img.dftsh.top
```

### 4.4 验证成功标准
- CDN证书到期时间与本地证书一致
- 日志中无ERROR级别报错
- 成功/失败域名统计正确

---

## 五、日常巡检方法

### 5.1 一键验证
```bash
bash /usr/local/bin/check_cdn_cert_validity.sh
```

### 5.2 查看同步日志
```bash
# 查看最近一次同步日志
tail -50 /var/log/certbot-cdn-sync.log

# 查看所有同步历史
grep "=== CDN Certificate Sync Process" /var/log/certbot-cdn-sync.log

# 查看失败记录
grep "ERROR\|FAIL" /var/log/certbot-cdn-sync.log | tail -20
```

### 5.3 证书有效期监控
```bash
# 计算剩余天数
cert_end_date=$(echo | openssl s_client -connect img.dftsh.top:443 -servername img.dftsh.top 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2)
end_epoch=$(date -d "$cert_end_date" +%s)
now_epoch=$(date +%s)
days_left=$(( (end_epoch - now_epoch) / 86400 ))
echo "CDN证书剩余天数: $days_left 天"
```

---

## 六、告警配置

### 6.1 企业微信机器人配置

1. 打开企业微信群，点击右上角「...」
2. 选择「群机器人」→「添加机器人」
3. 选择「自定义」机器人，设置名称（如：CDN证书监控）
4. 复制Webhook地址
5. 编辑 /etc/cdn_cert_alert_config：
   ```
   WECOM_WEBHOOK="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxxxx"
   ```

### 6.2 钉钉机器人配置

1. 打开钉钉群，点击「群设置」→「智能群助手」
2. 点击「添加机器人」→「自定义」
3. 设置机器人名称和安全设置（建议加签或关键词）
4. 复制Webhook地址
5. 编辑 /etc/cdn_cert_alert_config：
   ```
   DINGTALK_WEBHOOK="https://oapi.dingtalk.com/robot/send?access_token=xxxxxxxx"
   ```

### 6.3 测试告警

```bash
# 测试发送告警
bash /usr/local/bin/send_cert_alert.sh INFO "测试消息" "CDN证书监控告警测试"
```

### 6.4 告警场景

| 场景 | 级别 | 触发条件 |
|-----|------|---------|
| 同步成功 | INFO | 所有域名更新成功 |
| 同步失败 | ERROR | 任一域名更新失败 |
| 环境变量缺失 | ERROR | 启动时环境变量加载失败 |
| 证书文件异常 | ERROR | 本地证书读取失败 |

---

## 七、故障排查

### 7.1 常见错误

**错误1：CDN.0001 "The parameter https.https_switch is missing"**
- 原因：调用API时缺少https_switch参数
- 解决：确认脚本中包含 `--https.https_switch=1`

**错误2：证书内容格式错误**
- 原因：PEM换行符未正确转义
- 解决：脚本使用Python进行转义，确保内容完整

**错误3：权限不足**
- 原因：AK/SK缺少CDN相关权限
- 解决：在华为云IAM中为用户添加CDN相关策略

**错误4：CDN更新后验证仍是旧证书**
- 原因：CDN节点缓存，更新有延迟
- 解决：等待5-15分钟后再次验证，或清理本地DNS缓存

### 7.2 调试方法

```bash
# 1. 开启详细日志（脚本已默认输出详细信息）
# 查看完整日志
cat /var/log/certbot-cdn-sync.log

# 2. 手动测试单个步骤
# 测试证书读取
python3 -c "
with open('/etc/letsencrypt/live/wild_dftsh/fullchain.pem', 'r') as f:
    content = f.read()
print('Cert length:', len(content))
print('First line:', content.split(chr(10))[0])
"

# 3. 测试API调用（手动执行）
. /etc/huawei_cloud_env
hcloud configure set --region=cn-east-3 --domain-id="$HUAWEI_DOMAIN_ID" --access-key="$HUAWEI_AK" --secret-key="$HUAWEI_SK"
hcloud CDN ShowCertificatesHttpsInfo/v2 --domain_name=img.dftsh.top
```

---

## 八、回滚方案

如遇问题需回滚：

```bash
# 1. 移除crontab中的CDN同步任务
crontab -e
# 删除 ; /usr/local/bin/sync_huawei_cdn_cert.sh >> /var/log/certbot-cdn-sync.log 2>&1

# 2. 保留脚本不删除，停止自动执行即可

# 3. 如需恢复CDN证书，在华为云控制台手动重新上传
```

---

## 九、注意事项

1. **CDN更新延迟**：CDN证书更新后，全网节点生效需要5-15分钟，验证时请预留足够时间
2. **证书格式**：使用 `fullchain.pem`（含完整证书链），不要只用 `cert.pem`
3. **密钥安全**：AK/SK存放在 `/etc/huawei_cloud_env`，权限设为 600，禁止硬编码在脚本中
4. **日志轮转**：脚本内置10MB日志自动轮转，防止日志过大
5. **不影响现有流程**：本方案为新增环节，不修改原有Nginx和SCM同步逻辑
6. **重试机制**：失败自动重试3次，间隔10秒，提高成功率

---

## 十、相关文件路径汇总

| 用途 | 路径 |
|-----|------|
| 本地证书目录 | /etc/letsencrypt/live/wild_dftsh/ |
| 环境变量配置 | /etc/huawei_cloud_env |
| 告警配置 | /etc/cdn_cert_alert_config |
| CDN同步脚本 | /usr/local/bin/sync_huawei_cdn_cert.sh |
| 验证脚本 | /usr/local/bin/check_cdn_cert_validity.sh |
| 告警脚本 | /usr/local/bin/send_cert_alert.sh |
| 同步日志 | /var/log/certbot-cdn-sync.log |
| 原有SCM同步日志 | /var/log/certbot-dftsh-renew.log |
| 巡检日志 | /var/log/cdn-cert-check.log |
