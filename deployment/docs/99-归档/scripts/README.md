# 归档脚本说明

本目录包含已过时或一次性使用的部署脚本。

---

## 📦 归档内容

### migrate.ps1 - 数据迁移脚本

**用途：** 将本机数据迁移到 Docker 容器

**使用场景：**
- 首次从本机部署迁移到 Docker 部署
- 迁移 PostgreSQL、Redis、MinIO 数据

**为什么归档：**
- ⚠️ 一次性使用脚本
- 仅在首次迁移时需要
- 后续部署不再需要

**如何使用（如果需要）：**

```powershell
# 迁移所有数据
.\migrate.ps1 all

# 仅迁移 PostgreSQL
.\migrate.ps1 pg

# 仅迁移 Redis
.\migrate.ps1 redis

# 仅迁移 MinIO
.\migrate.ps1 minio
```

**注意事项：**
- 需要本机服务仍在运行
- 需要 Docker 容器已启动
- 会自动备份现有数据

---

### rollback.sh - 旧版回滚脚本

**用途：** Webhook 方案的回滚脚本

**为什么归档：**
- ❌ 已标记为 DEPRECATED
- 依赖 Webhook 方案的备份机制
- 已被 `rollback-ghcr.sh` 替代

**推荐替代方案：**

使用 `rollback-ghcr.sh` 进行回滚：

```bash
# 回滚到指定版本
./deployment/rollback-ghcr.sh v1.0.0

# 查看可回滚的版本
cat deployment/.cd-state/deploy-history.log
```

---

## ⚠️ 重要说明

**这些脚本已不再维护，不推荐使用。**

### 为什么归档？

1. **migrate.ps1** - 一次性迁移脚本，完成迁移后不再需要
2. **rollback.sh** - Webhook 方案已弃用，使用 GitHub Actions CD 方案

### 推荐方案

**数据迁移：**
- 使用 Docker 卷直接挂载现有数据目录
- 或使用数据库导入导出工具

**版本回滚：**
- 使用 `rollback-ghcr.sh` 脚本
- 查看 [日常维护手册](../../03-维护手册/日常维护手册.md) 的回滚章节

---

## 📅 归档时间

2026-04-26

---

**如需使用这些脚本，请先阅读脚本内容，了解其工作原理和注意事项。**
