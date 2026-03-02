from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, documents, search
from app.database import engine, Base

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="合同智能解读系统API",
    description="基于大语言模型的合同智能解读系统",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React开发服务器端口
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(documents.router, prefix="/api/documents", tags=["文档管理"])
app.include_router(search.router, prefix="/api/search", tags=["向量搜索"])

@app.get("/")
async def root():
    return {"message": "合同智能解读系统API", "status": "running"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}

