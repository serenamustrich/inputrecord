#!/bin/bash
# 卸载键盘监控服务

echo "🦐 键盘监控服务卸载器"
echo "======================"

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_DIR="$HOME/Library/LaunchAgents"

# 停止并卸载服务
echo ""
echo "🛑 停止服务..."
launchctl unload "$PLIST_DIR/com.keyboard-monitor.backend.plist" 2>/dev/null || true
launchctl unload "$PLIST_DIR/com.keyboard-monitor.frontend.plist" 2>/dev/null || true

# 删除 plist 文件
echo ""
echo "🗑️  删除配置文件..."
rm -f "$PLIST_DIR/com.keyboard-monitor.backend.plist"
rm -f "$PLIST_DIR/com.keyboard-monitor.frontend.plist"

echo ""
echo "======================"
echo "✅ 服务已卸载!"
echo ""
echo "服务将不再开机启动"
echo ""
