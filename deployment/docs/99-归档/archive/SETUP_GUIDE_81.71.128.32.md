# ~~腾讯云服务器 CD 配置指南（针对 81.71.128.32）~~

> **已废弃**：本文档记录的是腾讯云服务器上的旧 Webhook 部署路线，仅保留作历史参考。
> 当前推荐方案请查看 [CD_GITHUB_ACTIONS.md](./CD_GITHUB_ACTIONS.md)。

**你的情况**：
- ✅ 服务器已部署并运行
- ✅ 使用 GitHub 托管代码
- ✅ 只在版本标签变化时触发部署（如 v1.0 → v1.2）

---

## 🚀 一键配置（推荐）

### 在服务器上执行

```bash
# 1. SSH 登录服务器
ssh root@81.71.128.32

# 2. 下载配置脚本
cd /tmp
wget https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/pet_food_backend/pet-food/deployment/setup-cd.sh

# 或者从本地上传
# 在本地执行：scp pet_food_backend/pet-food/deployment/setup-cd.sh root@81.71.128.32:/tmp/

# 3. 执行一键配置脚本
bash /tmp/setup-cd.sh

# 4. 保存脚本输出的 Webhook 密钥（重要！）
```

脚本会自动完成：
- ✅ 安装 webhook 工具
- ✅ 创建部署脚本
- ✅ 生成 webhook 密钥
- ✅ 配置 systemd 服务
- ✅ 启动 webhook 服务

---

## 📝 手动配置（如果一键脚本失败）

### 步骤 1：安装 Webhook

```bash
ssh root@81.71.128.32

cd /tmp
wget https://github.com/adnanh/webhook/releases/download/2.8.1/webhook-linux-amd64.tar.gz
tar -xzf webhook-linux-amd64.tar.gz
sudo mv webhook-linux-amd64/webhook /usr/local/bin/
sudo chmod +x /usr/local/bin/webhook
webhook -version
```

### 步骤 2：创建目录和脚本

```bash
sudo mkdir -p /opt/petfood-cd
sudo mkdir -p /opt/petfood-backups

# 从项目复制脚本（假设项目在 /opt/petfood）
cd /opt/petfood
git pull  # 确保有最新的脚本

# 如果项目中没有脚本，手动创建（见 CD_TAG_BASED.md）
```

### 步骤 3：生成密钥并配置

```bash
# 生成 webhook 密钥
WEBHOOK_SECRET=$(openssl rand -hex 32)
echo "保存此密钥: $WEBHOOK_SECRET"

# 创建 hooks.json（将 YOUR_SECRET 替换为上面的密钥）
sudo nano /opt/petfood-cd/hooks.json
# 内容见 CD_TAG_BASED.md
```

### 步骤 4：启动服务

```bash
# 创建 systemd 服务
sudo nano /etc/systemd/system/petfood-webhook.service
# 内容见 CD_TAG_BASED.md

# 启动
sudo systemctl daemon-reload
sudo systemctl enable petfood-webhook
sudo systemctl start petfood-webhook
sudo systemctl status petfood-webhook
```

---

## 🔧 GitHub 配置

### 添加 Webhook

1. 打开你的 GitHub 仓库
2. **Settings** → **Webhooks** → **Add webhook**
3. 填写配置：

```
Payload URL: http://81.71.128.32:9000/hooks/deploy-petfood-tag
Content type: application/json
Secret: [粘贴你保存的 webhook 密钥]
```

4. **Which events would you like to trigger this webhook?**
   - 选择 **Let me select individual events**
   - ✅ 只勾选 **Branch or tag creation**
   - ❌ 取消其他所有选项

5. **Active**: ✅ 勾选
6. 点击 **Add webhook**

### 验证配置

GitHub 会自动发送 ping 请求，查看是否显示绿色 ✓。

---

## 🎯 使用方式

### 发布新版本

```bash
# 在本地开发机器上

# 1. 确保代码已提交
git add .
git commit -m "feat: 新功能完成"
git push origin main

# 2. 打版本标签
git tag -a v1.2.0 -m "Release version 1.2.0"

# 3. 推送标签（自动触发部署）
git push origin v1.2.0
```

### 查看部署进度

```bash
# SSH 登录服务器
ssh root@81.71.128.32

# 实时查看部署日志
tail -f /var/log/petfood-deploy.log

# 或查看 webhook 服务日志
sudo journalctl -u petfood-webhook -f
```

### 部署成功标志

日志中会显示：
```
✅ 部署成功！
   版本标签: v1.2.0
   提交: abc12345
   时间: 2026-04-24 15:30:00
```

---

## 🔄 回滚操作

### 方式 1：使用回滚脚本（推荐）

```bash
ssh root@81.71.128.32
sudo /opt/petfood-cd/rollback-tag.sh

# 按提示选择要回滚的版本
```

### 方式 2：手动回滚

```bash
ssh root@81.71.128.32
cd /opt/petfood

# 查看可用版本
git tag -l --sort=-version:refname | head -10

# 回滚到指定版本
git checkout tags/v1.1.0
cd pet_food_backend/pet-food
./deployment/deploy.sh restart
```

---

## 🔍 故障排查

### 问题 1：Webhook 未触发

**检查步骤**：

```bash
# 1. 检查服务状态
sudo systemctl status petfood-webhook

# 2. 查看服务日志
sudo journalctl -u petfood-webhook -n 50

# 3. 测试端口
curl http://localhost:9000/hooks/deploy-petfood-tag

# 4. 检查 GitHub Webhook 日志
# GitHub 仓库 → Settings → Webhooks → 点击你的 webhook → Recent Deliveries
```

**常见原因**：
- ❌ 服务未启动：`sudo systemctl start petfood-webhook`
- ❌ 端口被占用：`sudo lsof -i :9000`
- ❌ 防火墙阻止：`sudo ufw status`
- ❌ 密钥不匹配：检查 GitHub 和 hooks.json 中的密钥是否一致

### 问题 2：部署失败

```bash
# 查看详细日志
tail -100 /var/log/petfood-deploy.log

# 查看容器状态
cd /opt/petfood/pet_food_backend/pet-food
./deployment/deploy.sh ps
./deployment/deploy.sh logs api

# 检查磁盘空间
df -h

# 检查 Docker 状态
docker ps -a
```

### 问题 3：标签格式不匹配

当前配置只匹配 `v1.0.0` 格式（语义化版本）。

如果你使用 `v1.0` 或 `v1.2` 格式：

```bash
# 修改正则表达式
sudo nano /opt/petfood-cd/hooks.json

# 找到这行：
"regex": "^refs/tags/v[0-9]+\\.[0-9]+\\.[0-9]+$"

# 改为（匹配 v1.0 格式）：
"regex": "^refs/tags/v[0-9]+\\.[0-9]+$"

# 重启服务
sudo systemctl restart petfood-webhook
```

---

## 📊 监控和日志

### 查看部署历史

```bash
# 查看所有部署记录
grep "部署成功" /var/log/petfood-deploy.log

# 查看最近 5 次部署
grep "部署成功" /var/log/petfood-deploy.log | tail -5

# 查看今天的部署
grep "$(date +%Y-%m-%d)" /var/log/petfood-deploy.log
```

### 查看备份版本

```bash
# 列出所有备份
ls -lt /opt/petfood-backups/

# 查看备份详情
cat /opt/petfood-backups/backup-20260424-153000-v1.2.0.tag
cat /opt/petfood-backups/backup-20260424-153000-v1.2.0.commit
```

---

## 🔒 安全建议

### 1. 配置防火墙（推荐）

```bash
# 只允许 GitHub IP 访问 webhook 端口
sudo ufw allow from 140.82.112.0/20 to any port 9000 proto tcp
sudo ufw allow from 143.55.64.0/20 to any port 9000 proto tcp
sudo ufw allow from 192.30.252.0/22 to any port 9000 proto tcp
sudo ufw reload
```

### 2. 使用 Nginx 反向代理（更安全）

在 `/opt/petfood/pet_food_backend/pet-food/deployment/nginx/nginx.conf` 添加：

```nginx
location /webhook {
    allow 140.82.112.0/20;
    allow 143.55.64.0/20;
    allow 192.30.252.0/22;
    deny all;
    
    proxy_pass http://localhost:9000/hooks/deploy-petfood-tag;
}
```

然后 GitHub Webhook URL 改为：`http://81.71.128.32/webhook`

### 3. 启用 HTTPS（生产必须）

```bash
# 如果有域名，申请 SSL 证书
sudo certbot certonly --standalone -d your-domain.com

# 更新 .env.prod 中的 URL
# 重新部署
```

---

## ✅ 配置完成检查清单

- [ ] Webhook 工具已安装（`webhook -version`）
- [ ] 部署脚本已创建（`ls /opt/petfood-cd/`）
- [ ] Webhook 密钥已保存
- [ ] Webhook 服务已启动（`systemctl status petfood-webhook`）
- [ ] GitHub Webhook 已配置
- [ ] GitHub Webhook ping 测试通过（绿色 ✓）
- [ ] 推送测试标签验证部署成功
- [ ] 防火墙规则已配置（可选）
- [ ] 日志轮转已配置（可选）

---

## 📚 相关文档

- **[CD_TAG_BASED.md](./CD_TAG_BASED.md)** - 完整的基于标签的 CD 指南
- **[CD_GUIDE.md](./CD_GUIDE.md)** - 通用 CD 指南（包含 Cron 方案）
- **[README.md](./README.md)** - Docker 部署基础
- **[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)** - 部署故障排查

---

## 🎉 完成！

配置完成后，你的工作流程将是：

```bash
# 开发完成
git add .
git commit -m "feat: 新功能"
git push origin main

# 准备发布
git tag -a v1.2.0 -m "Release 1.2.0"
git push origin v1.2.0

# 🚀 自动部署到云服务器！
```

**需要帮助？**
- 查看日志：`tail -f /var/log/petfood-deploy.log`
- 查看服务：`systemctl status petfood-webhook`
- 手动回滚：`/opt/petfood-cd/rollback-tag.sh`
