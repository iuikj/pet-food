# 部署踩坑日志 & Lessons Learned

> 本文件是 2026-04-23 完整部署会话的经验沉淀。
> **面向读者**：未来接手这个项目的人（含 AI session）。
> **组织原则**：症状 → 根因 → 一句话修复 → 可直接执行的命令。

---

## 📍 环境版本锚点（务必三方对齐）

| 组件 | 统一版本 | 本机 | 容器 | 云服务器 |
|------|---------|------|------|---------|
| PostgreSQL | **17** | ✅ | `postgres:17-alpine` | 设 17 |
| Redis | **7.4.x** | 自查 | `redis:7-alpine` | 设 7 |
| MinIO | **RELEASE.2024-08-17T01-24-54Z** | ✅ | 同 release tag | 同 release tag |
| mc 客户端 | **RELEASE.2024-08-17T11-33-50Z** | 容器内 | 同 | 同 |

> **为什么三方对齐？** 跨版本兼容问题（如 `pg_dump` 17 产出 `SET transaction_timeout` 导 PG 16 失败）是最难快速排查的。统一版本 = 用一份 dump SQL 打所有环境。

---

## 🗂️ 常见问题速查表

| # | 关键症状 | 跳转 |
|---|---------|------|
| 1 | PowerShell 报 `字符串缺少终止符` 中文乱码 | [P1](#p1-powershell-51-gbk-编码陷阱) |
| 2 | `unable to prepare context: path ... not found` | [P2](#p2-docker-compose---project-directory-路径基准) |
| 3 | nginx 容器启动失败，配置文件变成目录 | [P3](#p3-docker-bind-mount-源缺失会偷建目录) |
| 4 | `/api/xxx.jpg` 404 从前端容器返回 | [P4](#p4-nginx-location-优先级正则--前缀) |
| 5 | `constraint "xxx_fkey" does not exist` 迁移失败 | [P5](#p5-alembic-autogenerate-约束名猜错) |
| 6 | `unrecognized configuration parameter "transaction_timeout"` | [P6](#p6-pg_dump-跨版本-set-语句不兼容) |
| 7 | `database files are incompatible with server` | [P7](#p7-pg-数据卷版本锁) |
| 8 | `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file` | [P8](#p8-docker-desktop-启动慢或未启动) |
| 9 | 镜像 pull 卡在 100% 好几千秒 | [P9](#p9-docker-hub-拉取卡顿) |
| 10 | 改了 `VITE_API_BASE_URL` 前端还用旧值 | [P10](#p10-前端-vite_-是编译期变量) |
| 11 | `POSTGRES_PASSWORD` 明明填了却报未设置 | [P11](#p11-env-文件特殊字符陷阱) |
| 12 | deploy.ps1 报 build 失败但没提示哪里 | [P12](#p12-脚本退出码检查必须到位) |

---

## 详细案例

### P1. PowerShell 5.1 GBK 编码陷阱

**症状**：
```
字符串缺少终止符: '
宸插彇娑?   ← 乱码
```

**根因**：Windows 中文系统的 PowerShell 5.1 默认按 GBK 读取无 BOM 的 `.ps1` 文件。Claude Code 的 Write 工具产出的是 UTF-8 **无 BOM**。中文被错误解码后尾字节经常撞上 `'`/`}`，把语法破坏。

**修复（选一）**：
- 【推荐】脚本字符串用 ASCII（英文）。注释可保中文（不参与语法分析）。
- 用 PowerShell 7（`pwsh`），默认 UTF-8。
- 手动把 `.ps1` 另存为 "UTF-8 with BOM"（VS Code 右下角切换编码）。

**何时会复发**：用普通文本工具向 `.ps1` 写入任何带中文的字符串字面量。

---

### P2. Docker Compose `--project-directory` 路径基准

**症状**：
```
unable to prepare context: path "E:\\frontend\\web-app" not found
```

**根因**：`docker compose --project-directory <DIR> -f xxx.yml` 会把 compose 里**所有相对路径**（build.context / volumes 源端 / env_file）都按 `<DIR>` 解析，**不是** compose 文件所在目录。

**本项目基准**：`--project-directory pet-food/`

**正确写法对照表**：

| 目的路径 | 应写 | 实际解析到 |
|---------|------|-----------|
| 后端镜像 build context (pet-food/) | `context: .` | `pet-food/` |
| 前端镜像 build context (Graduate/frontend/web-app/) | `context: ../../frontend/web-app` | `Graduate/frontend/web-app/` |
| nginx 配置文件 | `./deployment/nginx/nginx.conf` | `pet-food/deployment/nginx/nginx.conf` |

**自检**：站在 `pet-food/` 目录下，`ls <路径>` 能找到即对。

---

### P3. Docker bind mount 源缺失会"偷建目录"

**症状**：nginx 启动失败，因为 `/etc/nginx/nginx.conf` 被挂成了目录。

**根因**：Docker daemon 发现 bind-mount 源路径不存在时，**默认行为是创建一个同名目录**（假定你挂的是目录），然后把这个空目录挂到容器里。原本期望文件的容器进程就炸了。

**修复**：
```bash
# 1. 确认源路径真实存在
ls deployment/nginx/nginx.conf

# 2. 如果 Docker 已经偷建了占位目录（drwxr-xr-x 是目录，-rw- 才是文件）
ls -la <wrong-path>/
# 发现是目录 → 删除
rm -rf <wrong-path>

# 3. 修复 compose 里的路径（参考 P2）
```

**预防**：所有新加的 bind-mount 都先在宿主机上 `ls` 一遍源路径，确认是文件/目录类型正确。

---

### P4. Nginx location 优先级：正则 > 前缀

**症状**：头像上传成功，但 `GET /api/v1/pets/avatar/object/.../xxx.jpg` 返回 404，日志显示请求是 **frontend** 容器处理的（应该是 api 容器）。

**根因**：Nginx location 匹配优先级（高到低）：

1. `=` 精确匹配
2. `^~` 前缀匹配（阻止后续正则）
3. `~` / `~*` 正则匹配（按文件顺序，首个中的赢）
4. 无修饰符前缀匹配（最长）

原 `location /api/` 是无修饰符前缀，**优先级低于**同文件里的 `location ~* \.(jpg|png|...)$` 静态资源正则。当 API 返回 URL 以 `.jpg` 结尾时（预签名 URL / 代理对象 key）就被劫持到前端了。

**修复**：给业务路由前缀加 `^~`：
```nginx
location ^~ /api/       { proxy_pass http://fastapi_backend; ... }
location ^~ /minio-api/ { proxy_pass http://minio_api; ... }
```

**通用规则**：**任何要走特定 upstream 的业务路径都用 `^~`**，防止被同层正则按文件名/扩展名劫持。

---

### P5. Alembic autogenerate 约束名猜错

**症状**：
```
constraint "diet_plans_pet_id_fkey" of relation "diet_plans" does not exist
```

**根因**：SQLAlchemy 生成约束名的规则**因创建方式而异**：

| 创建方式 | PG 实际约束名 |
|---------|--------------|
| 建表时 `sa.ForeignKey(...)` 内联 | `<table>_<col>_fkey` |
| `batch_op.add_column(... sa.ForeignKey())` | 常为 `fk_<table>_<col>` 或匿名 |
| `op.create_foreign_key(name, ...)` 显式命名 | 你给的 name |

Alembic `autogenerate` 机械地假定第一种规则，但历史迁移用了第二种 → 名字对不上 → drop 失败。

**修复（幂等）**：改用按字段反查真实名字的辅助函数：
```python
from sqlalchemy import inspect

def _drop_fk_by_column(table: str, column: str) -> None:
    insp = inspect(op.get_bind())
    for fk in insp.get_foreign_keys(table):
        if column in (fk.get('constrained_columns') or []):
            name = fk.get('name')
            if name:
                op.drop_constraint(name, table, type_='foreignkey')
                return
    # 找不到也不报错，确保迁移幂等
```

已在 `alembic/versions/20260411_1612_53f28db7acbd_add_todo_items_table.py` 里落实。

**预防（根治）**：在 `src/db/base.py` 给 MetaData 加 `naming_convention`（见 [SQLAlchemy 文档](https://alembic.sqlalchemy.org/en/latest/naming.html)），从此所有约束名可预测。

---

### P6. pg_dump 跨版本 SET 语句不兼容

**症状**：
```
ERROR: unrecognized configuration parameter "transaction_timeout"
```

**根因**：`pg_dump` N 产出的 SQL 文件开头会写一组 `SET xxx=...` 固化环境，包含**版本专属参数**：

| 参数 | 引入版本 |
|------|---------|
| `transaction_timeout` | **PG 17** (PG 16 不认) |
| `idle_in_transaction_session_timeout` | PG 9.6 |
| `lock_timeout` | PG 9.3 |

`pg_dump` N 输出默认假定目标 ≥ N。N → N-1 会爆。

**修复（两层）**：
1. **治本**：版本对齐（见 P7 前半）。
2. **治标**：在 `migrate.ps1` 的 `Migrate-Seed` 里保留了自动剔除逻辑：
   ```powershell
   $unsupportedSets = @('transaction_timeout')
   foreach ($name in $unsupportedSets) {
       $raw = $raw -replace "(?mi)^SET\s+${name}\s*=.*\r?\n", ''
   }
   ```
   未来遇到新的跨版本不兼容 SET，往数组里加一个字符串即可。

---

### P7. PG 数据卷版本锁

**症状**：
```
FATAL: database files are incompatible with server
DETAIL: The data directory was initialized by PostgreSQL version 16, which is not compatible with this version 17.x
```

**根因**：PostgreSQL **不支持不同主版本之间的 data directory 向前/向后兼容**。一旦 data dir 被 PG N 初始化，就只能被 PG N 加载（或用 `pg_upgrade` 工具迁移）。

**修复**：
```powershell
# 1. 停容器
.\deployment\deploy.ps1 down

# 2. 确认旧卷名
docker volume ls | Select-String 'postgres'

# 3. 删除（只删 pg 卷，minio/redis 不动）
docker volume rm pet-food_postgres_data

# 4. 启动（新版本会初始化新 data dir）
.\deployment\deploy.ps1 up
```

**预防**：
- 升级 PG 主版本前：先 `pg_dumpall` 备份，再换镜像+清卷+重导入。
- 或用 `pg_upgrade` 做 in-place 升级（生产推荐，但要求本机双版本共存）。

---

### P8. Docker Desktop 启动慢或未启动

**症状**：
```
error during connect: Head "http://%2F%2F.%2Fpipe%2FdockerDesktopLinuxEngine/_ping":
  open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
```

**根因**：命名管道 `//./pipe/dockerDesktopLinuxEngine` 由 Docker Desktop 进程创建，服务没跑或 WSL2 后端还在启动 → 管道不存在。

**修复**：
1. 打开 Docker Desktop，等托盘鲸鱼停转圈（首启 30–60s）。
2. 验证：`docker info | Select-String 'Server Version'` 能打印版本号。
3. 不行就 Restart（右键托盘图标）。
4. 还不行查 `wsl --status` 看 WSL2 是否正常。

`deploy.ps1` 的 `Preflight` 已加此探活，失败会给出友好提示。

---

### P9. Docker Hub 拉取卡顿

**症状**：`docker compose pull` 某个镜像卡在 `100% Pulling` 数千秒。

**根因**：国内网络直连 Docker Hub 的 CDN 偶发被阻塞（表现为 metadata/layer 下载 0 字节或超长延迟）。

**修复**：给 Docker Desktop 配镜像加速器。Settings → Docker Engine → 合并：
```json
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://docker.1ms.run",
    "https://docker.mirrors.ustc.edu.cn",
    "https://dockerproxy.com"
  ]
}
```
Apply & Restart。验证：
```powershell
docker info | Select-String -Context 0,4 'Registry Mirrors'
```

**预防**：单镜像失败时，`docker pull <image>` 手动重试比让 compose 自动 pull 稳定（compose 不重试）。

---

### P10. 前端 `VITE_*` 是编译期变量

**症状**：修了 `.env.prod` 的 `VITE_API_BASE_URL` 后前端还用旧值。

**根因**：Vite 的 `VITE_*` 变量在 `vite build` 时被**静态替换**为字符串字面量写进 JS bundle。改环境变量后必须重新 build 前端镜像，否则 bundle 不变。

**修复**：
```powershell
.\deployment\deploy.ps1 down
docker image rm pet-food-frontend:latest   # 强制重 build
.\deployment\deploy.ps1 up
```

或者构建时显式传：
```powershell
docker compose -f deployment/docker-compose.prod.yml `
  --env-file deployment/.env.prod `
  build --no-cache frontend
```

**预防**：凡是 `VITE_*` 开头的 env，都要记住改完要 rebuild 前端镜像，不是 restart。

---

### P11. .env 文件特殊字符陷阱

**症状**：启动时 PG 报 `POSTGRES_PASSWORD not set`，但 `.env.prod` 里明明写了值。

**根因**：`docker compose --env-file` 的 KEY=VALUE 解析规则：
- `VALUE` 里有 `#` 会被当注释切断
- `VALUE` 里有空格没引号会被截断
- `VALUE` 里有 `$` 会被当变量展开

**修复**：含特殊字符的值**用单引号**包起来：
```
POSTGRES_PASSWORD='pa$$w#rd with space'
```

**预防**：
- 密码生成用 `python -c "import secrets; print(secrets.token_urlsafe(24))"` —— URL-safe 字符，天然无歧义。
- `deploy.ps1` 的 `Preflight` 已加必填项空值校验，会在启动前卡住缺失/为空的 key。

---

### P12. 脚本退出码检查必须到位

**症状**：`docker compose up -d` 失败，但脚本仍打印 `Deployment done. Entrypoints: ...` 误导用户。

**根因**：PowerShell 里调用外部命令后必须检查 `$LASTEXITCODE`，否则异常被吞。

**修复（已完成）**：`deploy.ps1` 的 `up` 分支现在：
1. `Compose up -d` 后立即检查 `$LASTEXITCODE`
2. 额外用 `docker inspect -f '{{.State.Status}}'` 逐服务确认 running
3. 任一不 running 就列表报错，拒绝打印 "All services healthy"

**通用原则**：任何 shell 脚本里调 Docker/Git/npm 命令，要么 `set -euo pipefail`（bash）、要么 `if ($LASTEXITCODE -ne 0)`（pwsh）。

---

## 📦 数据迁移最佳实践

### 场景 A：本机有"参考种子数据"（食材/补剂）要同步到容器 / 云端

使用 `migrate.ps1 seed`：
```powershell
$env:Path = "D:\DevelopFiles\PostgreSQL_17\bin;$env:Path"
.\deployment\migrate.ps1 seed `
    -PgSrcHost localhost `
    -PgSrcDb pet_food `
    -PgSrcPassword 'your_password'
```

**产物**：`deployment/backup_<timestamp>/seed_patched.sql` —— 幂等 SQL，可直接 scp 到云端一键导入：
```bash
cat seed_patched.sql | docker exec -i pet-food-postgres \
    psql -U petfood -d petfood -v ON_ERROR_STOP=1
```

**特性**：
- `ON CONFLICT (id) DO NOTHING` 保证幂等，重复跑不出事
- `session_replication_role='replica'` 临时跳过 FK 检查，避免外键顺序坑
- 仅影响 `-SeedTables` 参数指定的表，**不动业务数据**

### 场景 B：全库迁移（本机 ← → 容器）

三合一：`migrate.ps1 all`（实际业务很少需要，多用于初始化演示环境）。

### 场景 C：MinIO 数据零迁移

在 `.env.prod` 里设：
```
MINIO_DATA_PATH=D:\DevelopFiles\minio\data
```
版本对齐的前提下，容器直接 bind-mount 本机目录。**前提**：停掉本机 MinIO，避免双写。

---

## ✅ 上云前检查清单

```
[ ] .env.prod 所有 CHANGE_ME 已替换
[ ] .env.prod 未提交到 git（.gitignore 已排除）
[ ] registry-mirrors 已配置（国内服务器更重要）
[ ] 数据库版本对齐（本机 17 = 容器 17 = 云端 17）
[ ] Redis 版本对齐
[ ] MinIO 版本对齐
[ ] VITE_API_BASE_URL 改成云端域名 + 重 build 前端
[ ] MINIO_PUBLIC_ENDPOINT 改成云端可访问地址
[ ] CORS_ORIGINS 包含云端前端域名
[ ] ALLOWED_HOSTS 包含云端主机名
[ ] nginx.conf 启用 HTTPS 段（取消注释，配 Let's Encrypt）
[ ] 防火墙开放 22/80/443，关闭其他
[ ] 预备 2GB swap（4G 机器必备）
[ ] 备份脚本 cron 就绪（pg_dump + MinIO tar）
```

---

## 🧭 给未来 AI session 的快速上手指引

如果你是接手这个项目的 Claude Code session：

1. **读路线**：根 `CLAUDE.md` → `pet_food_backend/pet-food/CLAUDE.md` → 本文件
2. **三个不能改的命名错误**：`structrue_agent/`、`strtuct.py`、`TAVILIY_API_KEY`（不是 TAVILY），已在多处引用
3. **部署相关所有产物都在** `deployment/`：
   - `docker-compose.prod.yml` 是真相之源
   - `deploy.ps1` / `deploy.sh` 是包装脚本
   - `migrate.ps1` 是数据迁移工具（目前仅 seed 子命令被充分验证）
4. **常见操作一句话**：
   - 启动：`.\deployment\deploy.ps1 up`
   - 停止：`.\deployment\deploy.ps1 down`
   - 清库重来：`docker volume rm pet-food_postgres_data` 然后 up
   - 迁食材：`.\deployment\migrate.ps1 seed -PgSrcPassword '密码'`
5. **修改本文件的时机**：
   - 遇到新坑 → 按"症状→根因→修复"结构补一条
   - 版本锚点升级 → 更新顶部表格
   - 某条经验过时 → 用删除线 ~~旧做法~~ 而不是直接删（历史价值）
