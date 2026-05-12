#!/bin/bash
# 安装键盘监控为系统服务

echo "🦐 键盘监控服务安装器"
echo "======================"

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$SCRIPT_DIR/logs"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 复制 plist 文件到 LaunchAgents
echo ""
echo "📦 安装服务配置..."
cp "$SCRIPT_DIR/com.keyboard-monitor.backend.plist" "$PLIST_DIR/"
cp "$SCRIPT_DIR/com.keyboard-monitor.frontend.plist" "$PLIST_DIR/"

# 加载服务
echo ""
echo "🚀 加载服务..."
launchctl unload "$PLIST_DIR/com.keyboard-monitor.backend.plist" 2>/dev/null || true
launchctl load "$PLIST_DIR/com.keyboard-monitor.backend.plist"

launchctl unload "$PLIST_DIR/com.keyboard-monitor.frontend.plist" 2>/dev/null || true
launchctl load "$PLIST_DIR/com.keyboard-monitor.frontend.plist"

echo ""
echo "======================"
echo "✅ 服务安装完成!"
echo ""
echo "📊 仪表盘: http://127.0.0.1:1314"
echo "🔌 API:    http://127.0.0.1:65500"
echo "📝 日志:   $LOG_DIR/"
echo ""
echo "服务将在开机时自动启动"
echo ""
