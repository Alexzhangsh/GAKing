#!/bin/bash
cd /opt/gaking/deploy

# 清空Redis登录失败计数
docker compose exec -T redis redis-cli -a "e3m3-zM1NU8rodMU5pKENi66_7uFSo0Q" del "gaking:prod:auth:login_fail:admin" 2>/dev/null

# 登录
RESULT=$(curl -s -X POST http://127.0.0.1:3003/api/v1/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"alex@gak"}')
echo "登录: $(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'code={d.get(\"code\")}, msg={d.get(\"msg\")}')")"
TOKEN=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('token',''))")

if [ -n "$TOKEN" ]; then
  echo "角色管理: $(curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:3003/api/v1/admin/rbac/roles | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'code={d.get(\"code\")}, items={len(d.get(\"data\",{}).get(\"items\",[]))}')")"
  echo "管理员账号: $(curl -s -H "Authorization: Bearer $TOKEN" 'http://127.0.0.1:3003/api/v1/admin/rbac/users?page=1&page_size=10' | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'code={d.get(\"code\")}, items={len(d.get(\"data\",{}).get(\"items\",[]))}')")"
  echo "审计日志: $(curl -s -H "Authorization: Bearer $TOKEN" 'http://127.0.0.1:3003/api/v1/admin/audit/logs?page=1&page_size=10' | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'code={d.get(\"code\")}, items={len(d.get(\"data\",{}).get(\"items\",[]))}')")"
  echo "工作台-订单趋势: $(curl -s -H "Authorization: Bearer $TOKEN" 'http://127.0.0.1:3003/api/v1/admin/dashboard/order-trend?group_by=day&start_date=2026-08-01&end_date=2026-08-10' | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'code={d.get(\"code\")}, items={len(d.get(\"data\",{}).get(\"items\",[]))}')")"
  echo "工作台-佣金统计: $(curl -s -H "Authorization: Bearer $TOKEN" 'http://127.0.0.1:3003/api/v1/admin/dashboard/commission-stats?group_by=date&start_date=2026-08-01&end_date=2026-08-10' | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'code={d.get(\"code\")}, items={len(d.get(\"data\",{}).get(\"items\",[]))}')")"
  echo "工作台-提现趋势: $(curl -s -H "Authorization: Bearer $TOKEN" 'http://127.0.0.1:3003/api/v1/admin/dashboard/withdraw-trend?group_by=day&start_date=2026-08-01&end_date=2026-08-10' | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'code={d.get(\"code\")}, items={len(d.get(\"data\",{}).get(\"items\",[]))}')")"
  echo "用户管理: $(curl -s -H "Authorization: Bearer $TOKEN" 'http://127.0.0.1:3003/api/v1/admin/users-manage?page=1&page_size=10' | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'code={d.get(\"code\")}, items={len(d.get(\"data\",{}).get(\"items\",[]))}')")"
  echo "系统配置: $(curl -s -H "Authorization: Bearer $TOKEN" 'http://127.0.0.1:3003/api/v1/admin/config/' | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'code={d.get(\"code\")}, items={len(d.get(\"data\",{}).get(\"items\",[]))}')")"
else
  echo "TOKEN 获取失败"
fi