#!/bin/bash

# 遇到错误立即退出
set -e

echo "=================================================="
echo "🚀 开始一键部署 Cloud Judge 出题系统..."
echo "=================================================="

# 1. 检查运行目录
if [ ! -f "docker-compose.yml" ] || [ ! -d "backend" ]; then
    echo "❌ 错误: 未找到 docker-compose.yml 或 backend 目录。"
    echo "👉 请确保你在项目根目录 (api-problem-generator) 下运行此脚本！"
    exit 1
fi

CURRENT_DIR=$(pwd)
CURRENT_USER=$(whoami)

echo "📦 1. 更新系统软件包并安装基础依赖..."
sudo apt-get update
sudo apt-get install -y curl wget git python3 python3-pip python3-venv

echo "🐳 2. 检查并安装 Docker 环境..."
if ! command -v docker &> /dev/null; then
    echo "   ⏳ 正在安装 Docker..."
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker $CURRENT_USER
    echo "   ✅ Docker 安装完成"
else
    echo "   ✅ Docker 已安装"
fi

echo "🐍 3. 配置 Python 虚拟环境及 FastAPI 依赖..."
cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
# 激活虚拟环境并安装依赖
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cd ..
echo "   ✅ Python 环境配置完毕"

echo "🔥 4. 启动底层 C++ 编译与评测沙箱 (go-judge)..."
# 使用 docker compose 启动沙箱（自动寻找当前目录的 docker-compose.yml）
sudo docker compose up -d --build
echo "   ✅ go-judge 沙箱已在后台运行"

echo "⚙️ 5. 配置 FastAPI 生产级守护进程 (Systemd)..."
SERVICE_NAME="cloud-judge-api"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

# 动态生成 Systemd 配置文件
sudo bash -c "cat > $SERVICE_PATH" <<EOF
[Unit]
Description=Cloud Judge FastAPI Backend
After=network.target docker.service
Requires=docker.service

[Service]
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR/backend
Environment="PATH=$CURRENT_DIR/backend/venv/bin"
# 生产环境去掉了 --reload，提升性能
ExecStart=$CURRENT_DIR/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# 重载 systemd 并启动服务
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME
echo "   ✅ FastAPI 守护进程配置并启动完毕"

echo "=================================================="
echo "🎉 部署彻底完成！系统已上线！"
echo "=================================================="
echo "🌐 API 访问地址: http://<你的服务器IP>:8000/api/forge_problem"
echo ""
echo "🛠️ 日常运维命令:"
echo "  - 查看运行状态: sudo systemctl status $SERVICE_NAME"
echo "  - 查看实时日志: sudo journalctl -u $SERVICE_NAME -f"
echo "  - 重启 API 服务: sudo systemctl restart $SERVICE_NAME"
echo "=================================================="