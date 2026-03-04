# 快速启动指南

## 前置要求

- Python 3.9+
- Node.js 18+
- MySQL 8.0+ (或使用Docker)

## 方式一：使用启动脚本（推荐）

### Windows用户

1. **启动MySQL数据库**
   ```bash
   docker-compose up -d mysql
   ```
   或者使用本地MySQL，确保已创建数据库 `contract_ai`

2. **启动后端**
   ```bash
   start_backend.bat
   ```
   首次运行会自动创建虚拟环境和安装依赖

3. **启动前端**（新开一个终端）
   ```bash
   start_frontend.bat
   ```

### Linux/Mac用户

1. **启动MySQL数据库**
   ```bash
   docker-compose up -d mysql
   ```

2. **启动后端**
   ```bash
   chmod +x start_backend.sh
   ./start_backend.sh
   ```

3. **启动前端**（新开一个终端）
   ```bash
   chmod +x start_frontend.sh
   ./start_frontend.sh
   ```

## 方式二：手动启动

### 1. 准备MySQL数据库

#### 使用Docker（推荐）
```bash
docker-compose up -d mysql
```

#### 使用本地MySQL
```sql
CREATE DATABASE contract_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. 配置后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 创建.env文件
copy env.example .env  # Windows
# cp env.example .env  # Linux/Mac

# 编辑.env文件，配置数据库连接
# 默认配置：
# MYSQL_USER=root
# MYSQL_PASSWORD=password
# MYSQL_HOST=localhost
# MYSQL_PORT=3306
# MYSQL_DATABASE=contract_ai
# SECRET_KEY=your-secret-key-change-this
```

### 3. 启动后端

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端将在 http://localhost:8000 启动

### 4. 配置前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端将在 http://localhost:3000 启动

## 测试

### 1. 访问前端页面

打开浏览器访问：http://localhost:3000

### 2. 测试API接口

#### 使用测试脚本
```bash
python test_api.py
```

#### 使用curl
```bash
# 注册用户
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","password":"password123"}'

# 登录
curl -X POST "http://localhost:8000/api/auth/login" \
  -F "username=testuser" \
  -F "password=password123"
```

#### 使用Swagger UI
访问：http://localhost:8000/docs

## 常见问题

### 1. MySQL连接失败

**错误信息**：`(2003, "Can't connect to MySQL server")`

**解决方法**：
- 检查MySQL服务是否运行
- 检查`.env`文件中的数据库配置
- 确保数据库`contract_ai`已创建
- 如果使用Docker，检查容器是否运行：`docker ps`

### 2. 端口被占用

**错误信息**：`Address already in use`

**解决方法**：
- 后端：修改`uvicorn`命令中的端口，或关闭占用8000端口的程序
- 前端：修改`vite.config.js`中的端口配置

### 3. 前端无法连接后端

**解决方法**：
- 确保后端服务已启动
- 检查`vite.config.js`中的proxy配置
- 检查浏览器控制台的错误信息

### 4. 模块导入错误

**解决方法**：
- 确保已安装所有依赖：`pip install -r requirements.txt`
- 确保虚拟环境已激活
- 检查Python版本（需要3.9+）

## 下一步

完成第1-2天的功能后，可以继续开发：
- 第3-4天：文件上传与合同管理
- 第5-7天：RAG核心功能实现
- 第8-10天：智能问答功能




















