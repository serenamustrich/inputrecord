#!/bin/bash
# 备份键盘监控数据库

echo "📦 数据库备份工具"
echo "=================="

DB_PATH="/Users/chency/webot/keyboard_monitor/backend/keyboard_monitor.db"
BACKUP_DIR="/Users/chency/webot/keyboard_monitor/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/keyboard_monitor_$DATE.db"

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 检查数据库文件是否存在
if [ ! -f "$DB_PATH" ]; then
    echo "❌ 数据库文件不存在: $DB_PATH"
    exit 1
fi

# 备份数据库
cp "$DB_PATH" "$BACKUP_FILE"

# 检查备份是否成功
if [ -f "$BACKUP_FILE" ]; then
    SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
    echo "✅ 备份成功!"
    echo "📁 备份文件: $BACKUP_FILE"
    echo "📊 文件大小: $SIZE"
else
    echo "❌ 备份失败!"
    exit 1
fi

# 清理7天前的备份
echo ""
echo "🧹 清理旧备份..."
find "$BACKUP_DIR" -name "keyboard_monitor_*.db" -mtime +7 -delete 2>/dev/null
echo "✅ 清理完成"

echo ""
echo "=================="
echo "💡 恢复命令:"
echo "   cp $BACKUP_FILE $DB_PATH"
echo ""
