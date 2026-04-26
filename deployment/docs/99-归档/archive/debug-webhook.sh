# DEPRECATED: legacy webhook debug helper, kept only for historical troubleshooting.
# 检查 webhook 服务启动失败的原因

# 1. 查看详细日志
sudo journalctl -u petfood-webhook -n 50 --no-pager

# 2. 检查配置文件是否正确
cat /opt/petfood-cd/hooks.json

# 3. 手动测试 webhook 命令
/usr/local/bin/webhook -hooks /opt/petfood-cd/hooks.json -port 9000 -verbose

# 4. 检查端口是否被占用
sudo lsof -i :9000

# 5. 检查 webhook 版本
webhook -version
