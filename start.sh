#!/bin/bash
# 启动键盘监控服务

echo "🦐 键盘监控服务启动器"
echo "======================"

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# 检查Python依赖
echo ""
echo "📦 检查依赖..."
cd "$BACKEND_DIR"
pip3 install -q -r requirements.txt 2>/dev/null || pip install -q -r requirements.txt 2>/dev/null || true

# 启动后端
echo ""
echo "🚀 启动后端服务 (端口 65500)..."
cd "$BACKEND_DIR"
open Terminal > /dev/null 2>&1 &
python3 main.py &
BACKEND_PID=$!

# 等待后端启动
sleep 2

# 启动前端
echo ""
echo "🎨 启动前端服务 (端口 1314)..."
cd "$FRONTEND_DIR"
open Terminal > /dev/null 2>&1 &
python3 server.py &
FRONTEND_PID=$!

echo ""
echo "======================"
echo "✅ 服务已启动!"
echo ""
echo "📊 仪表盘: http://127.0.0.1:1314"
echo "🔌 API:    http://127.0.0.1:65500"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo ""

# 等待退出
wait
