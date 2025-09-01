#!/bin/bash

# logrotate 配置同步脚本
# 用途：将用户可编辑的 logrotate.user.conf 同步到系统配置 logrotate.conf

echo "=== logrotate 配置同步脚本 ==="
echo "时间: $(date)"
echo

# 检查用户配置文件是否存在
if [ ! -f "logrotate.user.conf" ]; then
    echo "❌ 错误：logrotate.user.conf 文件不存在"
    echo "请先创建用户配置文件"
    exit 1
fi

echo "📋 复制用户配置到系统配置..."
# 复制用户配置到系统配置文件
cp logrotate.user.conf logrotate.conf

echo "🔐 设置正确的权限和所有者..."
# 设置正确的权限和所有者
sudo chown root:root logrotate.conf
sudo chmod 644 logrotate.conf

echo "🧪 测试配置语法..."
# 测试配置
sudo /usr/sbin/logrotate -d logrotate.conf > /tmp/logrotate_sync_test.log 2>&1
if [ $? -eq 0 ]; then
    echo "✅ 配置语法正确"
    echo "📁 配置文件已同步：logrotate.user.conf → logrotate.conf"
    echo "🔄 logrotate 将在下次 cron 任务时生效（每 10 分钟检查一次）"
else
    echo "❌ 配置语法错误，请检查 logrotate.user.conf 文件"
    echo "错误详情："
    cat /tmp/logrotate_sync_test.log
    exit 1
fi

echo
echo "=== 同步完成 ==="
echo "💡 提示："
echo "  - 编辑配置：修改 logrotate.user.conf 文件"
echo "  - 同步配置：运行 ./sync_logrotate.sh"
echo "  - 手动轮转：sudo /usr/sbin/logrotate -f logrotate.conf"
echo "  - 测试配置：sudo /usr/sbin/logrotate -d logrotate.conf"