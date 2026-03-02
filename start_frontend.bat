@echo off
echo 启动前端服务...
cd frontend
if not exist node_modules (
    echo 安装依赖...
    call npm install
)
echo 启动开发服务器...
call npm run dev


