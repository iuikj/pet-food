# 部署指南

宠物饮食助手的 Docker 部署配置，支持本机测试和云服务器生产。

---

## 📚 文档导航

| 文档 | 用途 |
|------|------|
| **[README.md](./README.md)** (本文) | Docker 部署基础：环境配置、启动、迁移 |
| **[CD_GITHUB_ACTIONS.md](./CD_GITHUB_ACTIONS.md)** | **⭐ GitHub Actions CD 完整指南（技术细节）** |
| **[GITHUB_ACTIONS_QUICKSTART.md](../../GITHUB_ACTIONS_QUICKSTART.md)** | **🚀 5 步快速开始（推荐新手）** |
| **[GITHUB_ACTIONS_SETUP_GUIDE.md](../../GITHUB_ACTIONS_SETUP_GUIDE.md)** | **📋 详细配置指南（含故障排查）** |
| **[CD_IMPLEMENTATION_PLAN.md](../../CD_IMPLEMENTATION_PLAN.md)** | 实施计划和问题分析 |
| **[server-setup.sh](./server-setup.sh)** | 服务器一键准备脚本 |
| ~~[SETUP_GUIDE_81.71.128.32.md](./SETUP_GUIDE_81.71.128.32.md)~~ | 历史方案：腾讯云服务器的 Webhook 配置记录 |
| ~~[CD_TAG_BASED.md](./CD_TAG_BASED.md)~~ | 历史方案：基于标签的 Webhook CD |
| ~~[QUICK_START_CD.md](./QUICK_START_CD.md)~~ | 历史方案：5 分钟配置 Webhook/Cron |
| ~~[CD_GUIDE.md](./CD_GUIDE.md)~~ | 历史方案：Webhook/Cron 完整指南 |
| ~~[CD_PROGRESS_SUMMARY.md](./CD_PROGRESS_SUMMARY.md)~~ | 历史记录：Webhook 调试进度总结 |
| **[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)** | 部署踩坑日志（12 条案例） |

**快速开始 CD**：
- 🚀 **新手推荐**：[GITHUB_ACTIONS_QUICKSTART.md](../../GITHUB_ACTIONS_QUICKSTART.md) - 5 步完成配置
- 📋 **详细配置**：[GITHUB_ACTIONS_SETUP_GUIDE.md](../../GITHUB_ACTIONS_SETUP_GUIDE.md) - 含故障排查
- 📖 **技术细节**：[CD_GITHUB_ACTIONS.md](./CD_GITHUB_ACTIONS.md) - 完整的技术文档
- Webhook 相关文档仅作历史参考，不再继续扩展

---

## 一、目录结构

```
pet_food_backend/pet-food/
├── Dockerfile                       # 后端镜像
├── .dockerignore
├── deployment/
│   ├── docker-compose.prod.yml      # 服务编排（api + postgres + redis + minio + frontend + nginx）
│   ├── .env.prod.example            # 环境变量模板（复制后填写）
│   ├── entrypoint.sh                # API 容器入口：等 DB → 跑迁移 → 启 uvicorn
│   ├── deploy.sh                    # Linux/Mac/Git Bash 一键脚本
│   ├── deploy.ps1                   # Windows PowerShell 一键脚本
│   ├── docker-compose.cd.yml        # CD: GitHub Actions 覆盖 compose（GHCR 镜像）
│   ├── deploy-ghcr.sh               # CD: 服务器拉取 GHCR 镜像并更新 API
│   ├── rollback-ghcr.sh             # CD: API 镜像回滚脚本
│   ├── CD_GITHUB_ACTIONS.md         # CD: 当前推荐的 GitHub Actions 指南
│   ├── QUICK_START_CD.md            # 历史方案：Webhook/Cron 快速配置
│   ├── CD_GUIDE.md                  # 历史方案：Webhook/Cron 完整指南
│   ├── CD_TAG_BASED.md              # 历史方案：Tag + Webhook
│   ├── CD_PROGRESS_SUMMARY.md       # 历史记录：Webhook 调试总结
│   ├── deploy-webhook.sh            # 历史脚本：Webhook 触发部署
│   ├── deploy-cron.sh               # 历史脚本：定时拉取部署
│   ├── rollback.sh                  # 历史脚本：Webhook 方案回滚
│   ├── hooks.json                   # 历史模板：Webhook 配置
│   ├── petfood-webhook.service      # 历史模板：Webhook systemd 服务
│   ├── TROUBLESHOOTING.md           # 部署踩坑日志
│   └── nginx/
│       ├── nginx.conf               # 前端 + API + SSE + MinIO 代理
│       └── ssl/                     # 证书目录（上线后放）

frontend/web-app/
├── Dockerfile                       # 前端镜像（node build → nginx 静态托管）
└── .dockerignore
```

---

## 二、首次本机测试（5 步）

### 1. 准备环境变量

```bash
cd pet_food_backend/pet-food/deployment
cp .env.prod.example .env.prod
```

编辑 `.env.prod`，**至少**填写：

| 变量 | 说明 | 生成方式 |
|------|------|----------|
| `JWT_SECRET_KEY`、`SECRET_KEY` | 应用密钥 | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `POSTGRES_PASSWORD`、`REDIS_PASSWORD` | 数据库密码 | 自行生成强密码 |
| `MINIO_ROOT_USER`、`MINIO_ROOT_PASSWORD` | MinIO 管理员（密码 ≥ 8 位） | 自行设定 |
| `DASHSCOPE_API_KEY` | 阿里云 DashScope | 官网申请 |
| `TAVILIY_API_KEY` | Tavily 搜索 | 官网申请 |

> ⚠️ 脚本会检查是否还有 `CHANGE_ME` 占位，未替换会拒绝启动。

### 2. 启动

**Linux / Mac / Git Bash:**
```bash
chmod +x deploy.sh entrypoint.sh
./deploy.sh up
```

**Windows PowerShell:**
```powershell
.\deploy.ps1 up
```

首次构建需 5–10 分钟（前端 `npm ci` 较慢）。

### 3. 验证

| 入口 | URL | 期望 |
|------|-----|------|
| 前端 | http://localhost | React 应用首页 |
| API 文档 | http://localhost/docs | FastAPI Swagger |
| 健康检查 | http://localhost/health | `{"status":"ok"}` |
| MinIO Console | http://localhost:9001 | 登录后能看到 `petfood-bucket` |

### 4. 常用操作

```bash
./deploy.sh ps              # 查看容器 + 资源占用
./deploy.sh logs api        # 跟踪 API 日志
./deploy.sh logs            # 全部日志
./deploy.sh restart         # 重启
./deploy.sh shell api       # 进入 api 容器
./deploy.sh migrate         # 手动跑迁移
./deploy.sh down            # 停止（保留数据）
./deploy.sh clean           # 停止并删除所有卷（会丢数据！）
```

### 5. 测试 SSE 计划生成

1. 打开 http://localhost 注册账号
2. 完成 onboarding 创建宠物
3. 进入"创建计划"，观察是否有流式进度
4. 浏览器 DevTools → Network → 找 `/api/v1/plans/stream` 请求，应看到 `event-stream` 持续推送

---

## 三、资源占用参考（2C4G 机器）

空载时 `docker stats` 典型值：

| 容器 | 内存 | CPU |
|------|------|-----|
| api | 500–800 MB | <5% |
| postgres | 80–150 MB | <1% |
| redis | 20–40 MB | <1% |
| minio | 150–200 MB | <1% |
| frontend (nginx) | 10–20 MB | 0% |
| nginx (反代) | 10–20 MB | 0% |
| **合计** | **~1.2 GB** | — |

生成计划时 api 内存峰值 1.8–2.2 GB（4 个 week_agent 并行），总占用可达 **3.2–3.5 GB**。

---

## 四、从本机服务迁移数据到容器

已有本机在跑的 PostgreSQL / Redis / MinIO，想把数据搬进容器，用 `migrate.ps1`。

**前置条件**：
1. 容器已经 `deploy.ps1 up` 启动完毕
2. 本机原服务仍在运行（作为数据源）
3. 本机装有 `pg_dump` 和 `redis-cli`（MinIO 无需安装客户端）

### 4.1 三件套全量迁移（推荐）

```powershell
cd E:\Graduate\pet_food_backend\pet-food
.\deployment\migrate.ps1 all
```

脚本会按顺序处理 **PG → Redis → MinIO**，每步独立失败不影响其他。
所有产物落在 `deployment\backup_yyyyMMdd_HHmmss\`，包含源库 dump 和容器侧迁前快照，可用于回滚。

### 4.2 分步迁移

```powershell
# 仅迁 PostgreSQL（默认 5432/postgres/postgres/pet_food）
.\deployment\migrate.ps1 pg

# 自定义 PG 连接
.\deployment\migrate.ps1 pg -PgSrcUser admin -PgSrcPassword mypwd -PgSrcDb mydb

# 仅迁 Redis（脚本会交互式询问密码）
.\deployment\migrate.ps1 redis

# Redis 密码直接传参（避免交互）
.\deployment\migrate.ps1 redis -RedisSrcPassword 'your_password'

# 仅迁 MinIO（默认凭证 minioadmin/minioadmin）
.\deployment\migrate.ps1 minio

# 仅迁种子数据（食材 + 补剂），不碰用户/宠物/计划数据
.\deployment\migrate.ps1 seed

# 自定义种子表
.\deployment\migrate.ps1 seed -SeedTables 'ingredients','supplements','some_other_ref_table'
```

### 4.2.1 seed 子命令使用场景

> **典型场景**：本机有一份维护好的食材/补剂参考数据，想同步到**任何新库**（容器、测试环境、云服务器）而不影响该库已有的用户数据。

工作原理：

1. `pg_dump --data-only --column-inserts --table=ingredients --table=supplements` 导出纯 INSERT 语句（不含 schema）
2. 用正则把每条 `INSERT ...);` 改写为 `INSERT ...) ON CONFLICT (id) DO NOTHING;` → **幂等**，重复执行只会插入新增的行
3. 包进 `SET session_replication_role='replica'` 事务，临时跳过 FK 检查，导入过程不会被外键顺序问题打断
4. 通过 `docker exec psql` 管道导入容器
5. 自动校验每个表的行数

**特点**：
- ✅ 幂等：可以重复跑，不会产生重复数据
- ✅ 非破坏：只新增，不更新不删除
- ✅ 可扩展：通过 `-SeedTables` 参数支持任意参考表

**注意**：如果本机食材数据有 `user_id` 指向本机用户（user_id ≠ NULL），而容器库里没这些用户，导入仍会成功（ON CONFLICT 兜底），但可能影响食材归属展示。纯公共食材（user_id IS NULL）无此问题。

### 4.3 三种资源的迁移原理

| 资源 | 策略 | 原理 |
|------|------|------|
| **PostgreSQL** | `pg_dump → psql` 文本流 | 本机导 `.sql` 文件 → `docker exec` 管道进容器。本机库名 `pet_food` → 容器库名 `petfood`，用 `--no-owner` 绕过 role 差异 |
| **Redis** | `--rdb` 快照 + docker cp | 本机执行 `redis-cli --rdb` 让源主动保存并发送 RDB 文件 → 停容器清旧 AOF → `docker cp` 注入 → 重启容器加载 |
| **MinIO** | `mc mirror` 在线同步 | 用一次性 `minio/mc` 容器，通过 `host.docker.internal` 连本机源，跨 Docker 网络同步到 `minio:9000`。**版本完全对齐**（RELEASE.2024-08-17），元数据/加密/对象格式 100% 兼容 |

### 4.4 MinIO 的零迁移方案（更快）

如果你想**完全跳过 mc mirror**，直接让容器用本机的数据目录：

在 `.env.prod` 取消这行注释：
```
MINIO_DATA_PATH=D:\DevelopFiles\minio\data
```

然后重启：
```powershell
.\deployment\deploy.ps1 down
.\deployment\deploy.ps1 up
```

⚠️ 前提：`.env.prod` 里的 `MINIO_ROOT_USER` 和 `MINIO_ROOT_PASSWORD` **必须和本机一致**（`minioadmin/minioadmin`），否则新凭证覆盖旧凭证会锁住已有 bucket。

**优劣对比**：

| 维度 | bind mount（零迁移） | mc mirror |
|------|---------------------|-----------|
| 速度 | 瞬间 | 看数据量，GB 级数据数分钟 |
| 同时运行本机 MinIO | ❌ 必须停本机的 MinIO（端口/数据冲突） | ✅ 本机容器并存 |
| 可回滚 | ✅ 取消挂载即恢复 | ✅ 容器删除即恢复 |
| 适合 | 开发机，不再用原 MinIO | 保留本机原服务继续跑 |

### 4.5 迁移校验

```powershell
# PostgreSQL：对比表行数
docker exec pet-food-postgres psql -U petfood -d petfood -c `
    "SELECT 'users' t, count(*) FROM users UNION ALL SELECT 'pets', count(*) FROM pets"

# Redis：比较 key 数量（输入 .env.prod 里的密码）
docker exec pet-food-redis redis-cli -a <REDIS_PASSWORD> --no-auth-warning DBSIZE

# MinIO：对比 bucket 内文件数
docker exec pet-food-minio mc alias set local http://localhost:9000 <USER> <PWD>
docker exec pet-food-minio mc ls --recursive local/petfood-bucket | Measure-Object -Line
```

### 4.6 迁移常见错误

**Q: `pg_dump` 找不到命令**

加入 PATH 或临时使用：
```powershell
$env:Path += ";C:\Program Files\PostgreSQL\16\bin"
```

**Q: `redis-cli --rdb` 报 `NOAUTH`**

本机 Redis 有密码但没传。重跑时：
```powershell
.\deployment\migrate.ps1 redis -RedisSrcPassword 'your_real_password'
```

**Q: MinIO 迁移提示 `host.docker.internal` 连不上**

你的 Docker Desktop 版本可能不支持。改用宿主机 IP：
```powershell
# 查本机 IP
ipconfig | findstr IPv4
# 用 IP 重跑
.\deployment\migrate.ps1 minio -MinioSrcEndpoint http://192.168.x.x:9000
```

**Q: PG 导入报 `role "postgres" does not exist`**

脚本已加 `--no-owner --no-privileges` 避免此问题；若还出现，说明 dump 文件里有显式的 `ALTER ... OWNER TO postgres`。忽略警告即可，数据本身已成功导入。

**Q: Redis 迁完发现 key 数量对不上**

检查源侧是否用了多 DB（SELECT 1/2/3）。`--rdb` 默认只导 DB0。如需多 DB：
```powershell
redis-cli -a <pwd> -n 1 --rdb db1.rdb  # 手动每个 DB 单独导
```

---

## 五、切换到云服务器的变更点

如果你准备使用 **GitHub Actions + GHCR**，请优先阅读 [CD_GITHUB_ACTIONS.md](./CD_GITHUB_ACTIONS.md)。
当前方案会在后端 workflow 中额外 checkout 前端仓库 `iuikj/pet-food-frontend`，并一起构建前后端镜像。

本机配置迁到云服务器只需改 3 处：

### 1. 前端 API 基址（`.env.prod`）

```diff
- VITE_API_BASE_URL=http://localhost/api/v1
+ VITE_API_BASE_URL=https://your-domain.com/api/v1
```

### 2. MinIO 外部端点

```diff
- MINIO_PUBLIC_ENDPOINT=http://localhost:9000
+ MINIO_PUBLIC_ENDPOINT=https://your-domain.com/minio-api
- MINIO_CONSOLE_PUBLIC_URL=http://localhost:9001
+ MINIO_CONSOLE_PUBLIC_URL=https://your-domain.com/minio-console
```

并把 compose 里 MinIO 的 `127.0.0.1:9000:9000` 端口映射去掉（只走 Nginx 代理）。

### 3. Nginx 启用 HTTPS

取消 `nginx.conf` 底部 `server 443` 块的注释，配好 Let's Encrypt 证书：

```bash
docker run -it --rm \
  -v "$(pwd)/nginx/ssl:/etc/letsencrypt" \
  -v "/var/www/certbot:/var/www/certbot" \
  certbot/certbot certonly --webroot \
  -w /var/www/certbot -d your-domain.com
```

---

## 六、故障排查

**所有踩坑经验集中在 [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)**，含 12 条案例（PowerShell 编码、compose 路径基准、nginx location 优先级、Alembic 约束名、PG 跨版本、Docker Desktop 异常、镜像拉取卡顿、Vite 编译期变量等），每条按「症状 → 根因 → 一句话修复 → 可执行命令」结构给出。

**快速链接**：
- 脚本报错 "字符串缺少终止符" → [TROUBLESHOOTING #P1](./TROUBLESHOOTING.md#p1-powershell-51-gbk-编码陷阱)
- `unable to prepare context: path ... not found` → [#P2](./TROUBLESHOOTING.md#p2-docker-compose---project-directory-路径基准)
- 头像/静态资源被错误代理到前端 → [#P4](./TROUBLESHOOTING.md#p4-nginx-location-优先级正则--前缀)
- `constraint "xxx_fkey" does not exist` → [#P5](./TROUBLESHOOTING.md#p5-alembic-autogenerate-约束名猜错)
- `database files are incompatible with server` → [#P7](./TROUBLESHOOTING.md#p7-pg-数据卷版本锁)
- 改了 `VITE_*` 但前端没变 → [#P10](./TROUBLESHOOTING.md#p10-前端-vite_-是编译期变量)
- `.env.prod` 里填了值却被视为空 → [#P11](./TROUBLESHOOTING.md#p11-env-文件特殊字符陷阱)

新遇到的坑请按同样结构补到 TROUBLESHOOTING.md 末尾。

---

## 七、备份与恢复（上线必做）

### 备份脚本（每日 cron）

```bash
#!/bin/bash
# backup.sh
BACKUP_DIR=/var/backups/petfood/$(date +%Y%m%d)
mkdir -p "$BACKUP_DIR"

# PostgreSQL
docker exec pet-food-postgres pg_dump -U petfood petfood | gzip > "$BACKUP_DIR/pg.sql.gz"

# MinIO 数据
docker run --rm -v pet-food_minio_data:/data -v "$BACKUP_DIR:/backup" \
    alpine tar czf /backup/minio.tar.gz -C /data .

# 保留 7 天
find /var/backups/petfood -maxdepth 1 -type d -mtime +7 -exec rm -rf {} \;
```

### 恢复

```bash
# PostgreSQL
gunzip -c pg.sql.gz | docker exec -i pet-food-postgres psql -U petfood petfood

# MinIO
docker run --rm -v pet-food_minio_data:/data -v "$PWD:/backup" \
    alpine tar xzf /backup/minio.tar.gz -C /data
```

---

## 八、工程原则

本部署配置遵循：

- **KISS**：单 `.env.prod` + 单 compose，不引入 Kubernetes/Helm
- **DRY**：依赖源头统一在 `pyproject.toml`；前端构建参数单点传递
- **SOLID**：API / 前端 / 反代 / 存储 / 数据库 职责分离，可独立替换
- **YAGNI**：不预置 Milvus、APM、ELK，需要时再加
