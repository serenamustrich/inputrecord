#!/bin/bash
# 安全重启键盘监控服务

echo "🔄 安全重启服务"
echo "================"

# 先备份数据库
echo "📦 备份数据库..."
/Users/chency/webot/keyboard_monitor/backup_db.sh

echo ""
echo "🛑 停止服务..."

# 优雅停止服务
launchctl stop com.keyboard-monitor.backend 2>/dev/null
launchctl stop com.keyboard-monitor.frontend 2>/dev/null

# 等待进程退出
sleep 3

# 确认进程已停止
if pgrep -f "python3 main.py" > /dev/null; then
    echo "⚠️  进程未退出，强制停止..."
    lsof -ti:65500 | xargs kill -9 2>/dev/null
fi

if pgrep -f "python3 server.py" > /dev/null; then
    lsof -ti:1314 | xargs kill -9 2>/dev/null
fi

sleep 1

echo "🚀 启动服务..."
launchctl start com.keyboard-monitor.backend
launchctl start com.keyboard-monitor.frontend

sleep 2

echo ""
echo "================"
echo "✅ 服务已重启!"
echo ""

# 验证服务状态
launchctl list | grep keyboard
