@echo off
echo 启动后端服务...
cd backend
if not exist venv (
    echo 创建虚拟环境...
    python -m venv venv
)
call venv\Scripts\activate
if not exist .env (
    echo 创建.env文件...
    copy env.example .env
    echo 请编辑backend\.env文件配置数据库连接
    pause
)
echo 安装依赖...
pip install -r requirements.txt
echo 启动服务...
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
































