# SSL 证书说明

此目录用于存放生产环境的 SSL 证书文件。

## 文件说明

| 文件 | 说明 | 是否必需 |
|------|------|----------|
| `cert.pem` | SSL 证书文件 | 是（HTTPS） |
| `key.pem` | SSL 私钥文件 | 是（HTTPS） |
| `chain.pem` | 证书链文件 | 否 |

## 获取证书

### Let's Encrypt（免费）

```bash
sudo certbot certonly --nginx -d yourdomain.com
# 证书会保存到 /etc/letsencrypt/live/yourdomain.com/
# 复制到当前目录
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem key.pem
```

### 自签名证书（仅测试）

```bash
# 生成自签名证书（仅用于测试）
openssl req -x509 -newkey rsa:4096 -nodes \
  -keyout key.pem -out cert.pem -days 365 \
  -subj "/CN=localhost"
```

### 商业证书

将购买的 SSL 证书文件复制到此目录。

## 注意事项

⚠️ **请勿提交此目录中的真实证书到版本控制系统！**

此目录已添加到 `.dockerignore`，避免证书泄露到代码仓库。

## 证书续期

- Let's Encrypt 证书有效期为 90 天
- 建议配置自动续期
- 商业证书根据购买的有效期而定

续期命令示例：

```bash
# Let's Encrypt 自动续期
sudo certbot renew
sudo systemctl reload nginx
```
