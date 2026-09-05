# 金角大王 — 本地开发服务启动指令

> 适用场景：日常启动开发、更新代码后重启、关机前停止服务。

---

## 本地开发环境说明

| 服务 | 端口 | 状态 |
|------|------|------|
| Redis | 6379 | 已通过 Homebrew 安装并开机自启 |
| MySQL | 3306 | 使用远程开发库（121.37.173.132），无需本地部署 |
| 后端 FastAPI | 3001 | 需手动启动 |
| 管理后台 | 8080 | 需手动启动 |
| 小程序 H5 | 5173 | 需手动启动 |

> Redis 已在本地运行，无需通过 Docker 启动。

---

## 启动前准备：切换 Node.js 版本

前端项目（管理后台 + 小程序 H5）需要 **Node.js 18+**，你的电脑安装了 nvm 管理多版本 Node：

```bash
# 切换到 Node.js v18.20.8（已安装）
unset NPM_CONFIG_PREFIX && source ~/.nvm/nvm.sh && nvm use v18.20.8
```

> 每次新开终端都需要执行一次。建议将默认版本设为 v18：
> ```bash
> nvm alias default v18.20.8
> ```

---

## 启动服务

### 1. 启动后端

```bash
cd /Users/alexzhang/Documents/Work/Projects/Products/金角大王/GAKing-Coding/backend
source .venv/bin/activate && PYTHONPATH="." python src/main.py
```

验证：`curl http://localhost:3001/healthz` 返回 `{"status": "ok"}`

### 2. 启动管理后台（新开终端）

```bash
cd /Users/alexzhang/Documents/Work/Projects/Products/金角大王/GAKing-Coding/admin
unset NPM_CONFIG_PREFIX && source ~/.nvm/nvm.sh && nvm use v18.20.8 && npm run dev
```

浏览器访问：http://localhost:8080，默认账号 admin / admin@12345

### 3. 启动小程序 H5（新开终端）

```bash
cd /Users/alexzhang/Documents/Work/Projects/Products/金角大王/GAKing-Coding/miniprogram
unset NPM_CONFIG_PREFIX && source ~/.nvm/nvm.sh && nvm use v18.20.8 && npm run dev:h5
```

浏览器访问：http://localhost:5173

---

## 重启服务（代码更新后）

分别在各终端按 `Ctrl+C` 停止对应服务，再重新执行启动命令即可。

---

## 停止服务

| 操作 | 命令 |
|------|------|
| 停止后端 | 终端中按 `Ctrl+C` |
| 停止管理后台 | 终端中按 `Ctrl+C` |
| 停止小程序 H5 | 终端中按 `Ctrl+C` |
| 停止 Redis | `brew services stop redis` |

> 关机时 Redis 会自动随系统停止，无需手动操作。

---

## 验证服务状态

```bash
# 检查后端是否正常运行
curl http://localhost:3001/healthz

# 检查 Redis 是否运行
redis-cli ping
# 应返回 PONG

# 检查端口占用
lsof -i :3001    # 后端
lsof -i :8080    # 管理后台
lsof -i :5173    # 小程序 H5
lsof -i :6379    # Redis
```