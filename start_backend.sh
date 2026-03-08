#!/bin/bash
echo "启动后端服务..."
cd backend

if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

source venv/bin/activate

if [ ! -f ".env" ]; then
    echo "创建.env文件..."
    cp env.example .env
    echo "请编辑backend/.env文件配置数据库连接"
    read -p "按回车继续..."
fi

echo "安装依赖..."
pip install -r requirements.txt

echo "启动服务..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000































