# SSH 密钥对详解：公钥与私钥

详细解释 SSH 密钥对的生成、工作原理和安全最佳实践。

---

## 🔐 什么是 SSH 密钥对？

SSH 密钥对是一种**非对称加密**技术，由两个密钥组成：

| 密钥类型 | 文件名 | 作用 | 存放位置 |
|---------|--------|------|----------|
| **私钥** | `petfood_deploy_key` | 证明你的身份，**绝对保密** | 本地机器 + GitHub Secrets |
| **公钥** | `petfood_deploy_key.pub` | 验证私钥持有者，可以公开 | 服务器 `~/.ssh/authorized_keys` |

### 工作原理（简化版）

```
┌─────────────┐                    ┌─────────────┐
│  本地机器    │                    │   服务器     │
│             │                    │             │
│  私钥 🔑    │ ──── SSH 连接 ───→ │  公钥 🔓    │
│             │                    │             │
│  签名数据   │ ──── 发送签名 ───→ │  验证签名   │
│             │                    │             │
│             │ ←─── 允许登录 ──── │  验证通过 ✅ │
└─────────────┘                    └─────────────┘
```

**核心概念：**
1. 私钥可以生成签名，公钥可以验证签名
2. 私钥无法从公钥推导出来（数学上极难）
3. 只有持有私钥的人才能通过验证

---

## 📝 生成命令详解

### 完整命令

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/petfood_deploy_key
```

### 参数解释

| 参数 | 含义 | 说明 |
|------|------|------|
| `ssh-keygen` | SSH 密钥生成工具 | OpenSSH 自带的命令行工具 |
| `-t ed25519` | 密钥类型 | 使用 Ed25519 算法（推荐） |
| `-C "github-actions-deploy"` | 注释 | 标识这个密钥的用途 |
| `-f ~/.ssh/petfood_deploy_key` | 文件路径 | 指定密钥保存位置和文件名 |

### 密钥类型对比

| 算法 | 密钥长度 | 安全性 | 性能 | 推荐度 |
|------|---------|--------|------|--------|
| **Ed25519** | 256 位 | 极高 | 极快 | ⭐⭐⭐⭐⭐ 强烈推荐 |
| RSA | 2048-4096 位 | 高 | 较慢 | ⭐⭐⭐ 传统选择 |
| ECDSA | 256-521 位 | 高 | 快 | ⭐⭐⭐⭐ 较新 |
| DSA | 1024 位 | 低（已弃用） | 慢 | ❌ 不推荐 |

**为什么选择 Ed25519？**
- ✅ 密钥短（256 位），但安全性极高
- ✅ 生成和验证速度快
- ✅ 抗侧信道攻击
- ✅ 现代化算法，GitHub/GitLab 推荐

---

## 🔍 执行过程详解

### 步骤 1：执行生成命令

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/petfood_deploy_key
```

**会看到的提示：**

```
Generating public/private ed25519 key pair.
Enter passphrase (empty for no passphrase): 
```

**这里有两个选择：**

#### 选择 A：不设置密码（推荐用于自动化）

- 直接按 **Enter** 两次
- 优点：GitHub Actions 可以直接使用，无需输入密码
- 缺点：如果私钥泄露，任何人都能使用
- **适用场景**：自动化部署（本次场景）

#### 选择 B：设置密码（推荐用于个人使用）

- 输入一个强密码（至少 12 位）
- 优点：即使私钥泄露，没有密码也无法使用
- 缺点：每次使用都需要输入密码（不适合自动化）
- **适用场景**：个人开发机器

**本次场景推荐：不设置密码（直接按 Enter）**

### 步骤 2：生成完成

```
Your identification has been saved in /c/Users/你的用户名/.ssh/petfood_deploy_key
Your public key has been saved in /c/Users/你的用户名/.ssh/petfood_deploy_key.pub
The key fingerprint is:
SHA256:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx github-actions-deploy
The key's randomart image is:
+--[ED25519 256]--+
|        .o.      |
|       .  o      |
|      . .. .     |
|     . o. o      |
|    . o.S. .     |
|   . +.=o.o      |
|    =.B+o+       |
|   o.B=*+.       |
|    E*B*o.       |
+----[SHA256]-----+
```

**生成了两个文件：**

| 文件 | 类型 | 内容示例 |
|------|------|----------|
| `petfood_deploy_key` | 私钥 | `-----BEGIN OPENSSH PRIVATE KEY-----` |
| `petfood_deploy_key.pub` | 公钥 | `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA...` |

---

## 📂 查看密钥内容

### 查看私钥

```bash
cat ~/.ssh/petfood_deploy_key
```

**输出示例：**

```
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACBqL8xKJ5vZ3mH8xKJ5vZ3mH8xKJ5vZ3mH8xKJ5vZ3mHwAAAJgxKJ5vMSie
bwAAAAtzc2gtZWQyNTUxOQAAACBqL8xKJ5vZ3mH8xKJ5vZ3mH8xKJ5vZ3mH8xKJ5vZ3mHw
AAAEDxKJ5vZ3mH8xKJ5vZ3mH8xKJ5vZ3mH8xKJ5vZ3mH8xKJ5vZ3mH8xKJ5vZ3mH8xKJ5
vZ3mH8xKJ5vZ3mHwAAAAZnaXRodWItYWN0aW9ucy1kZXBsb3kBAgMEBQ==
-----END OPENSSH PRIVATE KEY-----
```

**⚠️ 重要：**
- 这是**完整的私钥内容**，包括 `-----BEGIN` 和 `-----END` 行
- 复制到 GitHub Secrets 时，**必须包含这两行**
- **绝对不要**分享给任何人或提交到代码仓库

### 查看公钥

```bash
cat ~/.ssh/petfood_deploy_key.pub
```

**输出示例：**

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGovzEonm9neYfzEonm9neYfzEonm9neYfzEonm9neYf github-actions-deploy
```

**格式说明：**
```
[算法类型] [公钥数据] [注释]
```

- `ssh-ed25519`: 算法类型
- `AAAAC3Nz...`: Base64 编码的公钥数据
- `github-actions-deploy`: 注释（你在 `-C` 参数中指定的）

---

## 🔧 配置到服务器

### 为什么要添加公钥到服务器？

服务器需要知道"哪些公钥是被信任的"，这样当有人用对应的私钥连接时，服务器才会允许登录。

### 添加公钥到服务器

```bash
# SSH 登录服务器
ssh root@81.71.128.32

# 添加公钥到 authorized_keys
echo "ssh-ed25519 AAAAC3Nz... github-actions-deploy" >> ~/.ssh/authorized_keys

# 设置正确的权限（重要！）
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh
```

**权限说明：**

| 文件/目录 | 权限 | 含义 | 为什么重要 |
|----------|------|------|-----------|
| `~/.ssh/` | `700` | 只有所有者可以读写执行 | SSH 要求目录权限严格 |
| `~/.ssh/authorized_keys` | `600` | 只有所有者可以读写 | 防止其他用户修改信任列表 |

**如果权限不正确，SSH 会拒绝使用这个文件！**

---

## 🧪 测试 SSH 连接

### 在本地测试

```bash
# 使用新生成的私钥连接服务器
ssh -i ~/.ssh/petfood_deploy_key root@81.71.128.32

# 如果成功，会直接登录，不需要输入密码
# 如果失败，检查：
# 1. 公钥是否正确添加到服务器
# 2. 服务器 authorized_keys 权限是否正确
# 3. 私钥文件权限是否正确（应该是 600）
```

### 设置私钥权限（如果需要）

```bash
# 私钥权限必须是 600（只有所有者可读写）
chmod 600 ~/.ssh/petfood_deploy_key
```

---

## 🔒 安全最佳实践

### 1. 私钥保护

| 做法 | 说明 |
|------|------|
| ✅ **专用密钥** | 为每个用途生成独立的密钥对 |
| ✅ **限制权限** | 私钥文件权限设为 `600` |
| ✅ **安全存储** | 存放在加密的文件系统中 |
| ✅ **定期轮换** | 每 6-12 个月更换一次 |
| ❌ **不要共享** | 绝不分享私钥给任何人 |
| ❌ **不要提交** | 绝不提交到 Git 仓库 |
| ❌ **不要复制** | 避免复制到多台机器 |

### 2. 公钥管理

| 做法 | 说明 |
|------|------|
| ✅ **添加注释** | 使用 `-C` 参数标识用途 |
| ✅ **记录位置** | 记录公钥部署在哪些服务器 |
| ✅ **定期审计** | 检查 `authorized_keys` 中的公钥 |
| ✅ **及时删除** | 不再使用的公钥要删除 |

### 3. GitHub Secrets 配置

```
配置 SERVER_SSH_KEY 时：

✅ 正确做法：
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAA...
（完整的私钥内容）
-----END OPENSSH PRIVATE KEY-----

❌ 错误做法：
- 只复制中间部分（缺少 BEGIN/END 行）
- 添加额外的空格或换行
- 复制成公钥内容
```

---

## 🎯 本次场景的完整流程

### 1. 本地生成密钥对

```bash
# 在 Windows Git Bash 执行
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/petfood_deploy_key

# 提示输入密码时，直接按 Enter（不设置密码）
```

### 2. 查看并复制私钥

```bash
# 查看私钥（稍后复制到 GitHub Secrets）
cat ~/.ssh/petfood_deploy_key

# 完整复制，包括 -----BEGIN 和 -----END 行
```

### 3. 查看并复制公钥

```bash
# 查看公钥（稍后添加到服务器）
cat ~/.ssh/petfood_deploy_key.pub

# 复制整行内容
```

### 4. 配置到服务器

```bash
# SSH 登录服务器
ssh root@81.71.128.32

# 添加公钥
echo "ssh-ed25519 AAAAC3Nz... github-actions-deploy" >> ~/.ssh/authorized_keys

# 设置权限
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh

# 退出
exit
```

### 5. 测试连接

```bash
# 在本地测试（应该不需要密码直接登录）
ssh -i ~/.ssh/petfood_deploy_key root@81.71.128.32

# 如果成功，输入 exit 退出
exit
```

### 6. 配置到 GitHub Secrets

1. 访问：`https://github.com/iuikj/pet-food/settings/secrets/actions`
2. 点击 **New repository secret**
3. Name: `SERVER_SSH_KEY`
4. Value: 粘贴步骤 2 复制的**完整私钥内容**
5. 点击 **Add secret**

---

## 🔍 常见问题

### Q1: 为什么要生成专用的密钥？

**A:** 安全隔离原则

- ✅ 如果这个密钥泄露，只影响部署，不影响你的个人账号
- ✅ 可以随时撤销这个密钥，不影响其他服务
- ✅ 可以设置不同的权限和限制

### Q2: 私钥泄露了怎么办？

**A:** 立即采取以下措施

1. **删除服务器上的公钥**
   ```bash
   ssh root@81.71.128.32
   nano ~/.ssh/authorized_keys
   # 删除对应的公钥行
   ```

2. **删除 GitHub Secret**
   - 访问 Secrets 页面
   - 删除 `SERVER_SSH_KEY`

3. **生成新的密钥对**
   - 重新执行生成步骤
   - 使用新的密钥重新配置

### Q3: 可以用同一个密钥对多个服务器吗？

**A:** 技术上可以，但不推荐

- ❌ 一个密钥泄露，所有服务器都受影响
- ❌ 无法单独撤销某个服务器的访问权限
- ✅ 推荐：每个服务器或每个用途使用独立的密钥对

### Q4: 为什么 GitHub Actions 能用这个私钥？

**A:** GitHub Secrets 的工作原理

1. 你把私钥存储在 GitHub Secrets 中
2. GitHub Actions 运行时，会把 Secret 注入到环境变量
3. `appleboy/ssh-action` 使用这个私钥连接服务器
4. 服务器验证私钥对应的公钥在 `authorized_keys` 中
5. 验证通过，允许连接

**整个过程中，私钥不会暴露在日志中！**

---

## 📚 延伸阅读

- [SSH 密钥类型对比](https://security.stackexchange.com/questions/5096/rsa-vs-dsa-for-ssh-authentication-keys)
- [Ed25519 算法详解](https://ed25519.cr.yp.to/)
- [GitHub SSH 密钥管理](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
- [OpenSSH 最佳实践](https://infosec.mozilla.org/guidelines/openssh)

---

**最后更新**: 2026-04-26  
**适用场景**: GitHub Actions 自动化部署
