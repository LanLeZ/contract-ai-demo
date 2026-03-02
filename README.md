# 合同智能解读系统

基于大语言模型的合同智能解读系统 - 15天MVP开发计划

## 项目结构

```
contract-ai-demo/
├── backend/              # FastAPI后端
│   ├── app/
│   │   ├── api/         # API路由
│   │   ├── models.py    # 数据库模型
│   │   ├── schemas.py   # Pydantic模式
│   │   ├── security.py  # 安全认证
│   │   ├── database.py  # 数据库配置
│   │   └── main.py      # 应用入口
│   ├── requirements.txt # Python依赖
│   └── .env.example     # 环境变量示例
├── frontend/            # React前端
│   ├── src/
│   │   ├── pages/       # 页面组件
│   │   ├── services/    # API服务
│   │   ├── hooks/       # React Hooks
│   │   └── App.jsx      # 应用入口
│   └── package.json     # 前端依赖
├── docker-compose.yml   # Docker配置
└── README.md           # 项目文档
```

## 功能清单（第1-2天完成）

- ✅ 用户注册
- ✅ 用户登录
- ✅ JWT认证
- ✅ 用户信息查询
- ✅ 前端登录注册页面
- ✅ 基础API接口测试

## 技术栈

### 后端
- FastAPI 0.104.1
- SQLAlchemy 2.0.23
- MySQL (PyMySQL)
- JWT认证 (python-jose)
- 密码加密 (passlib)

### 前端
- React 18.2.0
- Vite 5.0.8
- Ant Design 5.11.0
- React Router 6.20.0
- Axios 1.6.2

## 快速开始

### 前置要求

- Python 3.9+
- Node.js 18+
- MySQL 8.0+ (或使用Docker)
- Docker & Docker Compose (可选)

### 1. 启动MySQL数据库

#### 方式一：使用Docker（推荐）

```bash
docker-compose up -d mysql
```

#### 方式二：本地MySQL

确保MySQL已安装并运行，创建数据库：

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

# 复制环境变量文件
copy env.example .env  # Windows
# cp env.example .env  # Linux/Mac

# 编辑.env文件，配置数据库连接
# MYSQL_USER=root
# MYSQL_PASSWORD=password
# MYSQL_HOST=localhost
# MYSQL_PORT=3306
# MYSQL_DATABASE=contract_ai
# SECRET_KEY=your-secret-key-change-this
```

### 3. 启动后端服务

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端服务将在 http://localhost:8000 启动

### 4. 配置前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端服务将在 http://localhost:3000 启动

## API接口文档

启动后端后，访问以下地址查看API文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 认证接口

#### 1. 用户注册
```
POST /api/auth/register
Content-Type: application/json

{
  "username": "testuser",
  "email": "test@example.com",
  "password": "password123"
}
```

#### 2. 用户登录
```
POST /api/auth/login
Content-Type: multipart/form-data

username: testuser
password: password123
```

响应：
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

#### 3. 获取当前用户信息
```
GET /api/auth/me
Authorization: Bearer {token}
```

## 测试API接口

### 使用curl测试

#### 1. 注册用户
```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123"
  }'
```

#### 2. 用户登录
```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -F "username=testuser" \
  -F "password=password123"
```

#### 3. 获取用户信息（需要token）
```bash
curl -X GET "http://localhost:8000/api/auth/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 使用Python测试

创建 `test_api.py`:

```python
import requests

BASE_URL = "http://localhost:8000"

# 1. 注册
register_data = {
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123"
}
response = requests.post(f"{BASE_URL}/api/auth/register", json=register_data)
print("注册:", response.json())

# 2. 登录
login_data = {
    "username": "testuser",
    "password": "password123"
}
response = requests.post(
    f"{BASE_URL}/api/auth/login",
    data=login_data
)
token = response.json()["access_token"]
print("登录成功，Token:", token[:50] + "...")

# 3. 获取用户信息
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
print("用户信息:", response.json())
```

运行测试：
```bash
python test_api.py
```

## 数据库表结构

系统会自动创建以下表：

- `users`: 用户表
- `contracts`: 合同表（后续功能）
- `conversations`: 对话历史表（后续功能）

## 开发计划

- ✅ 第1-2天：用户登录注册功能
- ⏳ 第3-4天：文件上传与合同管理
- ⏳ 第5-7天：RAG核心功能实现
- ⏳ 第8-10天：智能问答功能
- ⏳ 第11-12天：简化版实体抽取
- ⏳ 第13-14天：UI优化与集成测试
- ⏳ 第15天：部署与文档

## 常见问题

### 1. MySQL连接失败

检查：
- MySQL服务是否运行
- `.env`文件中的数据库配置是否正确
- 数据库`contract_ai`是否已创建

### 2. 前端无法连接后端

检查：
- 后端服务是否在8000端口运行
- `vite.config.js`中的proxy配置是否正确
- CORS配置是否正确

### 3. JWT Token过期

默认token有效期为30天，如需修改，编辑`backend/app/security.py`中的`ACCESS_TOKEN_EXPIRE_MINUTES`

## 许可证

MIT License

