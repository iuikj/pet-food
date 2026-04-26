# 归档文档说明

本目录包含已过时的部署方案文档和脚本，仅供历史参考。

---

## 📦 归档内容

### Webhook 方案文档

- `CD_GITHUB_ACTIONS.md` - 旧版 GitHub Actions 指南
- `SETUP_GUIDE_81.71.128.32.md` - 腾讯云服务器 Webhook 配置
- `CD_TAG_BASED.md` - 基于标签的 Webhook CD
- `QUICK_START_CD.md` - Webhook/Cron 快速配置
- `CD_GUIDE.md` - Webhook/Cron 完整指南
- `CD_PROGRESS_SUMMARY.md` - Webhook 调试进度总结

### Webhook 方案脚本

- `deploy-webhook.sh` - Webhook 部署脚本
- `deploy-cron.sh` - Cron 定时部署脚本
- `debug-webhook.sh` - Webhook 调试脚本
- `hooks.json` - Webhook 配置文件
- `petfood-webhook.service` - Systemd 服务配置
- `webhook_sk.md` - Webhook 密钥说明
- `setup-cd.sh` - Webhook CD 安装脚本

---

## ⚠️ 重要说明

**这些文档和脚本已不再维护，不推荐使用。**

### 为什么弃用 Webhook 方案？

1. **安全性问题** - Webhook 需要暴露服务器端口，存在安全风险
2. **维护成本高** - 需要在服务器上运行额外的 Webhook 服务
3. **可靠性差** - 依赖服务器网络和 Webhook 服务稳定性
4. **功能受限** - 无法利用 GitHub Actions 的强大功能（并行构建、缓存等）

### 推荐方案

**使用 GitHub Actions CD 方案：**

- ✅ 更安全 - 通过 SSH 单向连接，无需暴露端口
- ✅ 更可靠 - 依赖 GitHub 基础设施
- ✅ 更强大 - 支持并行构建、缓存、矩阵测试等
- ✅ 更易维护 - 配置在代码仓库中，版本可控

**查看新文档：**

- [CD_QUICKSTART.md](../CD_QUICKSTART.md) - 5 步快速开始
- [CD_COMPLETE_GUIDE.md](../CD_COMPLETE_GUIDE.md) - 完整指南
- [CD_MAINTENANCE.md](../CD_MAINTENANCE.md) - 维护手册

---

## 📅 归档时间

2026-04-26

---

**如需查看这些文档，仅供学习和参考，不建议在生产环境使用。**
