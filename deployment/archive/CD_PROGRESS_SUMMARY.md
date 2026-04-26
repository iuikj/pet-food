# ~~CD 配置进度总结（2026-04-24）~~

> **历史记录**：本文档记录的是旧 Webhook 方案的中间进度，现已停止继续推进。
> 当前生产 CD 方案请查看 [CD_GITHUB_ACTIONS.md](./CD_GITHUB_ACTIONS.md)。
>
> **安全说明**：原文中出现过的 Webhook 密钥已视为废弃，不应继续使用。

本文档记录了为腾讯云服务器配置基于 Git Tag 的 CD 自动部署的完整进度。

---

## 📊 当前状态

### 服务器信息
- **服务器地址**: 81.71.128.32（腾讯云）
- **部署状态**: ✅ Docker 完整栈已部署并运行
- **项目路径**: `/opt/petfood`
- **Git 平台**: GitHub
- **仓库**: iuikj/pet-food

### CD 配置状态
- ✅ Webhook 工具已安装（v2.8.1）
- ✅ 部署脚本已创建（`/opt/petfood-cd/deploy-tag.sh`）
- ✅ 回滚脚本已创建（`/opt/petfood-cd/rollback-tag.sh`）
- ✅ Webhook 服务已启动（端口 9100）
- ✅ Systemd 服务已配置（`petfood-webhook.service`）
- ⚠️ **待解决**: Webhook 触发规则匹配问题

### 关键配置
- **Webhook 端口**: 9100（因 MinIO 占用 9000）
- **Webhook 密钥**: `已废弃，勿复用`
- **触发条件**: Git Tag 推送（格式 `v1.0.0`, `v1.3.0` 等）
- **GitHub Webhook URL**: `http://81.71.128.32:9100/hooks/deploy-petfood-tag`

---

## 📁 已创建的文件

### 服务器上（`/opt/petfood-cd/`）
```
/opt/petfood-cd/
├── hooks.json              # Webhook 配置文件
├── deploy-tag.sh           # 部署脚本（基于标签）
└── rollback-tag.sh         # 回滚脚本

/opt/petfood-backups/       # 备份目录（自动创建）

/etc/systemd/system/
└── petfood-webhook.service # Systemd 服务配置

/var/log/
└── petfood-deploy.log      # 部署日志（自动创建）
```

### 本地项目（`E:\Graduate\pet_food_backend\pet-food\deployment\`）
```
deployment/
├── CD_GUIDE.md                      # 通用 CD 完整指南
├── CD_TAG_BASED.md                  # 基于标签的 CD 详细文档
├── QUICK_START_CD.md                # 5 分钟快速配置
├── SETUP_GUIDE_81.71.128.32.md      # 针对此服务器的定制指南
├── setup-cd.sh                      # 一键配置脚本
├── deploy-webhook.sh                # Webhook 部署脚本模板
├── deploy-cron.sh                   # Cron 部署脚本模板
├── rollback.sh                      # 回滚脚本模板
├── hooks.json                       # Webhook 配置模板
└── petfood-webhook.service          # Systemd 服务模板
```

---

## ✅ 已完成的步骤

### 1. 服务器环境配置
```bash
# 已执行
- 安装 webhook 工具（v2.8.1）
- 创建 CD 目录（/opt/petfood-cd, /opt/petfood-backups）
- 生成 webhook 密钥
```

### 2. 脚本创建
```bash
# 已创建并赋予执行权限
/opt/petfood-cd/deploy-tag.sh      # 部署脚本
/opt/petfood-cd/rollback-tag.sh    # 回滚脚本
/opt/petfood-cd/hooks.json         # Webhook 配置
```

### 3. Systemd 服务配置
```bash
# 已配置并启动
sudo systemctl enable petfood-webhook
sudo systemctl start petfood-webhook
# 状态: active (running)
```

### 4. 端口调整
```bash
# 原因: MinIO 占用 9000 端口
# 解决: 改用 9100 端口
# 验证: sudo lsof -i :9100  # webhook 正常监听
```

### 5. GitHub Webhook 配置
```
URL: http://81.71.128.32:9100/hooks/deploy-petfood-tag
Content type: application/json
Secret: 已废弃，勿复用
Events: Branch or tag creation (仅此一项)
```

---

## ⚠️ 当前问题

### 问题描述
推送标签后，GitHub Webhook 返回 400 错误：
```
Hook rules were not satisfied.
```

### 测试情况
```bash
# 本地推送
git tag -a v1.3.0 -m "Test CD deployment"
git push origin v1.3.0

# GitHub 响应
HTTP 400 Bad Request
Body: Hook rules were not satisfied.
```

### 可能原因
1. **正则表达式转义问题** - JSON 中的反斜杠转义可能不正确
2. **Payload 格式不匹配** - GitHub 发送的 payload 结构与配置不符
3. **签名验证失败** - HMAC-SHA256 签名计算或验证有问题
4. **事件类型不匹配** - GitHub 发送的事件类型与预期不符

### 调试步骤（待执行）
```bash
# 1. 查看 webhook 实时日志
sudo journalctl -u petfood-webhook -f

# 2. 查看 GitHub 实际发送的 payload
# GitHub 仓库 → Settings → Webhooks → Recent Deliveries

# 3. 手动测试
curl -X POST http://localhost:9100/hooks/deploy-petfood-tag \
  -H "Content-Type: application/json" \
  -d '{"ref":"refs/tags/v1.3.0"}'

# 4. 使用最简化配置测试
# 见下方"临时调试配置"
```

---

## 🔧 临时调试配置

### 最简化配置（用于定位问题）

```bash
# 创建最简单的配置，去掉所有验证
sudo tee /opt/petfood-cd/hooks.json > /dev/null <<'EOF'
[
  {
    "id": "deploy-petfood-tag",
    "execute-command": "/opt/petfood-cd/deploy-tag.sh",
    "command-working-directory": "/opt/petfood",
    "response-message": "Deployment triggered",
    "pass-arguments-to-command": [
      {
        "source": "payload",
        "name": "ref"
      }
    ]
  }
]
EOF

sudo systemctl restart petfood-webhook
```

**说明**: 此配置去掉了所有触发规则，任何请求都会触发部署。仅用于测试 webhook 是否能正常接收请求和执行脚本。

### 逐步添加规则

**步骤 1: 只验证 ref 字段存在**
```json
{
  "trigger-rule": {
    "match": {
      "type": "value",
      "value": "refs/tags/v1.3.0",
      "parameter": {
        "source": "payload",
        "name": "ref"
      }
    }
  }
}
```

**步骤 2: 使用正则匹配**
```json
{
  "trigger-rule": {
    "match": {
      "type": "regex",
      "regex": "^refs/tags/v.*$",
      "parameter": {
        "source": "payload",
        "name": "ref"
      }
    }
  }
}
```

**步骤 3: 添加签名验证**
```json
{
  "trigger-rule": {
    "and": [
      {
        "match": {
          "type": "payload-hmac-sha256",
          "secret": "已废弃，勿复用",
          "parameter": {
            "source": "header",
            "name": "X-Hub-Signature-256"
          }
        }
      },
      {
        "match": {
          "type": "regex",
          "regex": "^refs/tags/v.*$",
          "parameter": {
            "source": "payload",
            "name": "ref"
          }
        }
      }
    ]
  }
}
```

---

## 📝 下一步操作

### 立即执行
1. **查看 GitHub Webhook 日志**
   - GitHub 仓库 → Settings → Webhooks → 点击 webhook → Recent Deliveries
   - 查看 Request headers, Request body, Response
   - 截图或复制 payload 内容

2. **查看服务器 webhook 日志**
   ```bash
   sudo journalctl -u petfood-webhook -n 100 --no-pager
   ```

3. **使用最简化配置测试**
   ```bash
   # 应用上面的"最简化配置"
   # 重新推送标签测试
   ```

### 问题解决后
1. **恢复完整配置**（包含签名验证和正则匹配）
2. **配置防火墙规则**（限制只允许 GitHub IP 访问）
3. **配置 Nginx 反向代理**（使用 80 端口，更安全）
4. **配置 HTTPS**（生产环境必须）
5. **配置通知**（企业微信/钉钉，可选）

---

## 🔒 安全配置（待完成）

### 1. 防火墙规则
```bash
# 只允许 GitHub IP 访问 9100 端口
sudo ufw allow from 140.82.112.0/20 to any port 9100 proto tcp
sudo ufw allow from 143.55.64.0/20 to any port 9100 proto tcp
sudo ufw allow from 192.30.252.0/22 to any port 9100 proto tcp
```

### 2. Nginx 反向代理（推荐）
```nginx
# 在 /opt/petfood/pet_food_backend/pet-food/deployment/nginx/nginx.conf
# server 块中添加：

location /webhook {
    # 只允许 GitHub IP
    allow 140.82.112.0/20;
    allow 143.55.64.0/20;
    allow 192.30.252.0/22;
    deny all;
    
    proxy_pass http://host.docker.internal:9100/hooks/deploy-petfood-tag;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Hub-Signature-256 $http_x_hub_signature_256;
}
```

然后：
```bash
docker exec pet-food-nginx nginx -s reload
```

GitHub Webhook URL 改为：`http://81.71.128.32/webhook`

### 3. HTTPS 配置
```bash
# 申请 SSL 证书（需要域名）
sudo certbot certonly --standalone -d your-domain.com

# 更新 .env.prod
VITE_API_BASE_URL=https://your-domain.com/api/v1
MINIO_PUBLIC_ENDPOINT=https://your-domain.com/minio-api

# 重新部署
cd /opt/petfood/pet_food_backend/pet-food
./deployment/deploy.sh restart
```

---

## 📚 相关文档

### 本地文档（`E:\Graduate\pet_food_backend\pet-food\deployment\`）
- **SETUP_GUIDE_81.71.128.32.md** - 针对此服务器的完整配置指南
- **CD_TAG_BASED.md** - 基于标签的 CD 详细技术文档
- **CD_GUIDE.md** - 通用 CD 指南（包含 Webhook 和 Cron 方案）
- **TROUBLESHOOTING.md** - 部署故障排查（12 条案例）

### 在线资源
- [Webhook 官方文档](https://github.com/adnanh/webhook)
- [GitHub Webhooks 文档](https://docs.github.com/en/webhooks)

---

## 🛠️ 常用命令

### 服务管理
```bash
# 查看服务状态
sudo systemctl status petfood-webhook

# 重启服务
sudo systemctl restart petfood-webhook

# 查看日志
sudo journalctl -u petfood-webhook -f

# 查看部署日志
tail -f /var/log/petfood-deploy.log
```

### 配置修改
```bash
# 编辑 webhook 配置
sudo nano /opt/petfood-cd/hooks.json

# 编辑 systemd 服务
sudo nano /etc/systemd/system/petfood-webhook.service

# 重新加载配置
sudo systemctl daemon-reload
sudo systemctl restart petfood-webhook
```

### 手动部署
```bash
# 手动触发部署
sudo /opt/petfood-cd/deploy-tag.sh refs/tags/v1.3.0

# 手动回滚
sudo /opt/petfood-cd/rollback-tag.sh
```

### 调试
```bash
# 测试 webhook 端点
curl -X POST http://localhost:9100/hooks/deploy-petfood-tag \
  -H "Content-Type: application/json" \
  -d '{"ref":"refs/tags/v1.3.0"}'

# 查看端口占用
sudo lsof -i :9100

# 查看进程
ps aux | grep webhook
```

---

## 📊 部署流程图

```
开发者本地
    ↓ git tag -a v1.3.0 -m "Release"
    ↓ git push origin v1.3.0
GitHub
    ↓ POST http://81.71.128.32:9100/hooks/deploy-petfood-tag
    ↓ X-Hub-Signature-256: sha256=...
    ↓ {"ref":"refs/tags/v1.3.0", ...}
Webhook 服务 (端口 9100)
    ↓ 验证签名
    ↓ 匹配触发规则
    ↓ 执行 /opt/petfood-cd/deploy-tag.sh
部署脚本
    ↓ 1. 备份当前版本
    ↓ 2. git fetch --tags
    ↓ 3. git checkout tags/v1.3.0
    ↓ 4. docker compose build
    ↓ 5. docker compose up -d
    ↓ 6. 健康检查 (30 次重试)
    ↓ 7. 成功 → 清理旧镜像
    ↓    失败 → 自动回滚
完成
    ↓ 记录日志 /var/log/petfood-deploy.log
    ↓ 可选：发送通知（企业微信/钉钉）
```

---

## 🎯 成功标志

部署成功后，日志中会显示：

```
[2026-04-24 18:30:00] ==========================================
[2026-04-24 18:30:00] 🚀 开始部署 Pet Food - 版本: v1.3.0
[2026-04-24 18:30:00] ==========================================
[2026-04-24 18:30:01] 📦 备份当前版本: backup-20260424-183000-v1.3.0
[2026-04-24 18:30:02] 📥 拉取标签 v1.3.0...
[2026-04-24 18:30:03] 🔄 切换到标签 v1.3.0...
[2026-04-24 18:30:04] 📝 版本更新: abc12345 -> def67890
[2026-04-24 18:30:05] 🔨 构建 Docker 镜像...
[2026-04-24 18:32:30] 🔄 更新服务...
[2026-04-24 18:32:40] ⏳ 等待服务启动...
[2026-04-24 18:32:50] 🏥 健康检查...
[2026-04-24 18:32:52] ✅ 健康检查通过
[2026-04-24 18:32:53] 🧹 清理旧镜像...
[2026-04-24 18:32:54] ==========================================
[2026-04-24 18:32:54] ✅ 部署成功！
[2026-04-24 18:32:54]    版本标签: v1.3.0
[2026-04-24 18:32:54]    提交: def67890
[2026-04-24 18:32:54]    时间: 2026-04-24 18:32:54
[2026-04-24 18:32:54] ==========================================
```

---

## 📞 联系信息

- **项目**: Pet Food 宠物饮食计划智能助手
- **服务器**: 腾讯云 81.71.128.32
- **配置日期**: 2026-04-24
- **配置人**: [你的名字]

---

## 🔄 版本历史

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-04-24 | v1.0 | 初始配置，Webhook 服务已启动，待解决触发规则问题 |

---

**最后更新**: 2026-04-24 18:30:00  
**状态**: ⚠️ 配置中（Webhook 触发规则调试中）
