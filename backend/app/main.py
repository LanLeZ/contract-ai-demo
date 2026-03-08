from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, documents, search, qa, kg, compare
from app.database import engine, Base

import logging
import sys

LOG_LEVEL = logging.INFO  # 如果想看 debug 就改成 logging.DEBUG

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

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

from fastapi import FastAPI

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(documents.router, prefix="/api/documents", tags=["文档管理"])
app.include_router(search.router, prefix="/api/search", tags=["向量搜索"])
app.include_router(qa.router, prefix="/api", tags=["智能问答"])
app.include_router(kg.router, prefix="/api", tags=["知识图谱"])
app.include_router(compare.router, prefix="/api", tags=["合同对比"])

@app.get("/")
async def root():
    return {"message": "合同智能解读系统API", "status": "running"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}

