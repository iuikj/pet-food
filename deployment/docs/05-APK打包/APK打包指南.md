# Android APK 打包指南

> 使用 GitHub Actions 自动构建 Android APK

---

## 📋 目录

- [一、概述](#一概述)
- [二、配置步骤](#二配置步骤)
- [三、使用方式](#三使用方式)
- [四、签名配置](#四签名配置)
- [五、故障排查](#五故障排查)

---

## 一、概述

### 1.1 工作流程

```
推送标签 v*.*.*
    ↓
GitHub Actions 触发
    ↓
1. Checkout 前端代码
2. 安装 Node.js + Java + Android SDK
3. 构建 Web 应用 (Vite)
4. Sync Capacitor
5. 构建 APK (Debug + Release)
6. 上传到 Artifacts
7. 创建 GitHub Release
```

### 1.2 输出产物

- **Debug APK** - 用于测试，未签名
- **Release APK** - 用于发布，已签名（需要配置 Keystore）

---

## 二、配置步骤

### 2.1 前置条件

- ✅ 前端仓库已配置 Capacitor
- ✅ 有 GitHub 仓库的 Admin 权限
- ✅ （可选）有 Android 签名证书

### 2.2 配置 GitHub Secrets

访问：`https://github.com/你的用户名/pet-food/settings/environments`

点击 **pet-food** environment，添加以下 Secrets：

#### 必需的 Secrets

| Secret 名称 | 说明 | 示例值 |
|------------|------|--------|
| `FRONTEND_REPOSITORY_TOKEN` | 前端仓库访问 Token | GitHub PAT |

#### 可选的 Secrets（用于 Release 签名）

| Secret 名称 | 说明 | 如何获取 |
|------------|------|----------|
| `ANDROID_KEYSTORE_FILE` | Keystore 文件（Base64） | 见下方 |
| `ANDROID_KEYSTORE_PASSWORD` | Keystore 密码 | 创建 Keystore 时设置 |
| `ANDROID_KEY_ALIAS` | Key 别名 | 创建 Keystore 时设置 |
| `ANDROID_KEY_PASSWORD` | Key 密码 | 创建 Keystore 时设置 |

---

## 三、使用方式

### 3.1 自动触发（推荐）

```bash
# 1. 确保前后端都打了相同的标签
# 后端
cd pet_food_backend/pet-food
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0

# 前端
cd frontend/web-app
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0

# 2. GitHub Actions 自动触发
# 访问：https://github.com/你的用户名/pet-food/actions
```

### 3.2 手动触发

1. 访问：`https://github.com/你的用户名/pet-food/actions/workflows/build-android.yml`
2. 点击 **Run workflow**
3. 输入版本号（如 `v1.0.0`）
4. 点击 **Run workflow**

### 3.3 下载 APK

**方式 1：从 Artifacts 下载**

1. 访问：`https://github.com/你的用户名/pet-food/actions`
2. 点击对应的 workflow run
3. 在 **Artifacts** 部分下载 APK

**方式 2：从 GitHub Release 下载**

1. 访问：`https://github.com/你的用户名/pet-food/releases`
2. 找到对应的版本
3. 下载 APK 文件

---

## 四、签名配置

### 4.1 为什么需要签名？

- **Debug APK** - 可以直接安装测试，但不能发布到应用商店
- **Release APK** - 需要签名才能发布到 Google Play 或其他应用商店

### 4.2 创建 Keystore

```bash
# 使用 keytool 创建 Keystore
keytool -genkey -v -keystore release.keystore \
  -alias pet-food \
  -keyalg RSA \
  -keysize 2048 \
  -validity 10000

# 按提示输入信息：
# - Keystore 密码（记住，后面要用）
# - Key 密码（记住，后面要用）
# - 组织信息（CN、OU、O、L、ST、C）
```

**重要：** 妥善保管 `release.keystore` 文件和密码！丢失后无法更新应用！

### 4.3 转换为 Base64

```bash
# Linux/Mac
base64 release.keystore > release.keystore.base64

# Windows PowerShell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("release.keystore")) > release.keystore.base64
```

### 4.4 配置到 GitHub Secrets

1. 复制 `release.keystore.base64` 的内容
2. 访问：`https://github.com/你的用户名/pet-food/settings/environments`
3. 点击 **pet-food** environment
4. 添加以下 Secrets：
   - `ANDROID_KEYSTORE_FILE` - 粘贴 Base64 内容
   - `ANDROID_KEYSTORE_PASSWORD` - Keystore 密码
   - `ANDROID_KEY_ALIAS` - Key 别名（如 `pet-food`）
   - `ANDROID_KEY_PASSWORD` - Key 密码

---

## 五、故障排查

### 5.1 构建失败

**症状：** GitHub Actions 显示构建失败

**排查步骤：**

```bash
# 1. 查看 GitHub Actions 日志
# 访问：https://github.com/你的用户名/pet-food/actions

# 2. 本地测试构建
cd frontend/web-app
npm install
npm run build
npx cap sync android
cd android
./gradlew assembleDebug
```

### 5.2 前端标签不存在

**症状：** "Error: The process '/usr/bin/git' failed with exit code 1"

**解决方案：**

```bash
# 确保前端仓库有对应的标签
cd frontend/web-app
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

### 5.3 签名失败

**症状：** Release APK 构建失败

**可能原因：**
1. Keystore 文件 Base64 编码错误
2. 密码或别名错误
3. Keystore 文件损坏

**解决方案：**

```bash
# 验证 Keystore 文件
keytool -list -v -keystore release.keystore

# 重新生成 Base64
base64 release.keystore > release.keystore.base64

# 重新配置 GitHub Secrets
```

### 5.4 Gradle 构建超时

**症状：** "Gradle build timeout"

**解决方案：**

在 `android/gradle.properties` 中增加内存：

```properties
org.gradle.jvmargs=-Xmx4096m -XX:MaxPermSize=512m
org.gradle.daemon=true
org.gradle.parallel=true
```

---

## 六、本地构建 APK

如果需要在本地构建 APK：

```bash
# 1. 进入前端目录
cd frontend/web-app

# 2. 安装依赖
npm install

# 3. 构建 Web 应用
npm run build

# 4. 同步到 Android
npx cap sync android

# 5. 打开 Android Studio
npx cap open android

# 6. 在 Android Studio 中：
# Build -> Build Bundle(s) / APK(s) -> Build APK(s)

# 或使用命令行：
cd android
./gradlew assembleDebug    # Debug APK
./gradlew assembleRelease  # Release APK（需要签名配置）
```

**APK 输出位置：**
- Debug: `android/app/build/outputs/apk/debug/app-debug.apk`
- Release: `android/app/build/outputs/apk/release/app-release.apk`

---

## 七、发布到应用商店

### 7.1 Google Play

1. 访问：https://play.google.com/console
2. 创建应用
3. 上传 Release APK
4. 填写应用信息
5. 提交审核

### 7.2 其他应用商店

- **华为应用市场** - https://developer.huawei.com/consumer/cn/
- **小米应用商店** - https://dev.mi.com/
- **OPPO 软件商店** - https://open.oppomobile.com/
- **vivo 应用商店** - https://dev.vivo.com.cn/

---

## 八、版本管理

### 8.1 版本号规范

在 `android/app/build.gradle` 中配置：

```gradle
android {
    defaultConfig {
        versionCode 1        // 整数，每次发布递增
        versionName "1.0.0"  // 语义化版本号
    }
}
```

### 8.2 自动化版本号

可以在 workflow 中自动更新版本号：

```yaml
- name: Update version
  working-directory: frontend/web-app/android/app
  run: |
    VERSION="${{ github.ref_name }}"
    VERSION_CODE=$(date +%s)
    sed -i "s/versionName \".*\"/versionName \"$VERSION\"/" build.gradle
    sed -i "s/versionCode .*/versionCode $VERSION_CODE/" build.gradle
```

---

## 九、相关文档

- [快速开始指南](../01-快速开始/快速开始指南.md) - CD 配置
- [完整部署指南](../02-完整指南/完整部署指南.md) - 详细配置
- [日常维护手册](../03-维护手册/日常维护手册.md) - 运维操作
- [返回主文档](../../README.md) - 文档导航

---

## 十、常见问题

### Q1: Debug APK 和 Release APK 有什么区别？

**A:** 
- **Debug APK** - 未签名，可以直接安装测试，但不能发布
- **Release APK** - 已签名，可以发布到应用商店

### Q2: 如何在手机上安装 APK？

**A:**
1. 下载 APK 文件到手机
2. 在手机设置中允许"安装未知来源应用"
3. 点击 APK 文件安装

### Q3: 为什么需要前后端都打标签？

**A:** 
- 后端标签触发 CD 部署
- 前端标签用于构建 APK
- 保持版本号一致，方便管理

### Q4: Keystore 文件丢失了怎么办？

**A:** 
- ⚠️ **无法恢复！** Keystore 丢失后无法更新应用
- 只能重新创建 Keystore，作为新应用发布
- **务必备份 Keystore 文件和密码！**

---

**文档维护：** 如有问题或改进建议，请提交 Issue 或 PR。

**最后更新：** 2026-04-26
