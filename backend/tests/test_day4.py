"""
第四天功能测试
测试文档解析、文件上传、向量搜索等功能
"""
import os
import sys
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app
from app.database import get_db, Base, engine
from app import models
from app.security import get_password_hash
from app.services.document_parser import DocumentParser
from app.services.text_splitter import LawTextSplitter
from app.services.vector_store import VectorStore


# 项目根目录 & 测试用真实合同文件路径
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REAL_CONTRACT_PATH = PROJECT_ROOT / "data" / "contract" / "internship" / "internship1.docx"


# 创建测试客户端
client = TestClient(app)

# 测试用的用户凭证
TEST_USERNAME = "test_user_day4"
TEST_PASSWORD = "test_password_123"
TEST_EMAIL = "test_day4@example.com"

# 测试token
test_token = None


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """设置测试数据库"""
    # 创建所有表
    Base.metadata.create_all(bind=engine)
    yield
    # 清理（可选）


@pytest.fixture(scope="module")
def test_user():
    """创建测试用户"""
    db = next(get_db())
    
    # 检查用户是否已存在
    user = db.query(models.User).filter(models.User.username == TEST_USERNAME).first()
    if user:
        # 先删除关联的 contracts（避免外键约束错误）
        db.query(models.Contract).filter(models.Contract.user_id == user.id).delete()
        # 先删除关联的 conversations
        db.query(models.Conversation).filter(models.Conversation.user_id == user.id).delete()
        # 然后删除用户
        db.delete(user)
        db.commit()
    
    # 创建新用户
    hashed_password = get_password_hash(TEST_PASSWORD)
    user = models.User(
        username=TEST_USERNAME,
        email=TEST_EMAIL,
        password_hash=hashed_password
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    yield user
    
    # 清理（可选，如果需要在测试后清理）
    # 注意：清理时也要先删除关联数据
    # db.query(models.Contract).filter(models.Contract.user_id == user.id).delete()
    # db.query(models.Conversation).filter(models.Conversation.user_id == user.id).delete()
    # db.delete(user)
    # db.commit()
    db.close()


@pytest.fixture(scope="module")
def auth_token(test_user):
    """获取认证token"""
    global test_token
    
    response = client.post(
        "/api/auth/login",
        data={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    test_token = data["access_token"]
    return test_token


class TestDocumentParser:
    """测试文档解析器"""
    
    def test_parse_markdown(self):
        """测试Markdown文件解析"""
        parser = DocumentParser()
        
        # 创建临时Markdown文件
        test_content = "# 测试标题\n\n这是测试内容。"
        test_file = Path("./test_temp.md")
        test_file.write_text(test_content, encoding='utf-8')
        
        try:
            result = parser.parse(str(test_file), file_type='md')
            assert "测试标题" in result
            assert "测试内容" in result
        finally:
            if test_file.exists():
                test_file.unlink()
    
    def test_detect_file_type(self):
        """测试文件类型检测"""
        parser = DocumentParser()
        
        assert parser._detect_file_type("test.pdf") == "pdf"
        assert parser._detect_file_type("test.docx") == "docx"
        assert parser._detect_file_type("test.md") == "md"
        assert parser._detect_file_type("test.markdown") == "md"
    
    def test_parse_unsupported_type(self):
        """测试不支持的文件类型"""
        parser = DocumentParser()
        
        with pytest.raises(ValueError):
            parser.parse("test.txt", file_type="txt")


class TestFileUpload:
    """测试文件上传API"""
    
    def test_upload_without_auth(self):
        """测试未认证上传（应该失败）"""
        test_file_content = b"# Test Contract\n\nThis is test content."
        
        response = client.post(
            "/api/documents/upload",
            files={"file": ("test.md", test_file_content, "text/markdown")}
        )
        
        assert response.status_code == 401
    
    def test_upload_docx(self, auth_token):
        """测试上传docx文件（使用真实合同文件）"""
        assert REAL_CONTRACT_PATH.exists(), f"测试合同文件不存在: {REAL_CONTRACT_PATH}"
        
        with open(REAL_CONTRACT_PATH, "rb") as f:
            response = client.post(
                "/api/documents/upload",
                headers={"Authorization": f"Bearer {auth_token}"},
                files={
                    "file": (
                        "internship1.docx",
                        f,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["filename"] == "internship1.docx"
        assert "upload_time" in data
        
        return data["id"]
    
    def test_upload_invalid_type(self, auth_token):
        """测试上传不支持的文件类型"""
        test_file_content = b"test content"
        
        response = client.post(
            "/api/documents/upload",
            headers={"Authorization": f"Bearer {auth_token}"},
            files={"file": ("test.txt", test_file_content, "text/plain")}
        )
        
        assert response.status_code == 400
        assert "不支持的文件类型" in response.json()["detail"]
    
    def test_get_documents_list(self, auth_token):
        """测试获取文档列表"""
        response = client.get(
            "/api/documents/",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_document_detail(self, auth_token):
        """测试获取文档详情"""
        # 先上传一个真实合同文件
        assert REAL_CONTRACT_PATH.exists(), f"测试合同文件不存在: {REAL_CONTRACT_PATH}"
        
        with open(REAL_CONTRACT_PATH, "rb") as f:
            upload_response = client.post(
                "/api/documents/upload",
                headers={"Authorization": f"Bearer {auth_token}"},
                files={
                    "file": (
                        "internship1.docx",
                        f,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
        
        contract_id = upload_response.json()["id"]
        
        # 获取详情
        response = client.get(
            f"/api/documents/{contract_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == contract_id
        assert data["filename"] == "internship1.docx"
    
    def test_delete_document(self, auth_token):
        """测试删除文档"""
        # 先上传一个真实合同文件
        assert REAL_CONTRACT_PATH.exists(), f"测试合同文件不存在: {REAL_CONTRACT_PATH}"
        
        with open(REAL_CONTRACT_PATH, "rb") as f:
            upload_response = client.post(
                "/api/documents/upload",
                headers={"Authorization": f"Bearer {auth_token}"},
                files={
                    "file": (
                        "internship1.docx",
                        f,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
        
        contract_id = upload_response.json()["id"]
        
        # 删除文档
        response = client.delete(
            f"/api/documents/{contract_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 204
        
        # 验证文档已删除
        get_response = client.get(
            f"/api/documents/{contract_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert get_response.status_code == 404


class TestVectorSearch:
    """测试向量搜索API"""
    
    def test_search_without_auth(self):
        """测试未认证搜索（应该失败）"""
        response = client.post(
            "/api/search/",
            json={"query": "测试查询", "top_k": 5}
        )
        
        assert response.status_code == 401
    
    def test_search_documents(self, auth_token):
        """测试向量搜索"""
        # 先上传一个真实合同文件以便搜索
        assert REAL_CONTRACT_PATH.exists(), f"测试合同文件不存在: {REAL_CONTRACT_PATH}"
        
        with open(REAL_CONTRACT_PATH, "rb") as f:
            upload_response = client.post(
                "/api/documents/upload",
                headers={"Authorization": f"Bearer {auth_token}"},
                files={
                    "file": (
                        "internship1.docx",
                        f,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
        
        # 等待向量化完成（实际应用中可能需要异步处理）
        import time
        time.sleep(3)
        
        # 执行搜索
        response = client.post(
            "/api/search/",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "query": "薪资待遇",
                "top_k": 5,
                "source_type": "contract"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert "results" in data
        assert "total" in data
        assert isinstance(data["results"], list)
    
    def test_search_by_contract(self, auth_token):
        """测试按合同搜索"""
        # 先上传一个真实合同文件
        assert REAL_CONTRACT_PATH.exists(), f"测试合同文件不存在: {REAL_CONTRACT_PATH}"
        
        with open(REAL_CONTRACT_PATH, "rb") as f:
            upload_response = client.post(
                "/api/documents/upload",
                headers={"Authorization": f"Bearer {auth_token}"},
                files={
                    "file": (
                        "internship1.docx",
                        f,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
        
        contract_id = upload_response.json()["id"]
        
        # 等待向量化完成
        import time
        time.sleep(3)
        
        # 按合同搜索
        response = client.post(
            "/api/search/by-contract",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "query": "薪资待遇",
                "contract_id": contract_id,
                "top_k": 5
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert "results" in data
        assert len(data["results"]) > 0
    
    def test_search_empty_query(self, auth_token):
        """测试空查询"""
        response = client.post(
            "/api/search/",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"query": "", "top_k": 5}
        )
        
        assert response.status_code == 400
        assert "查询内容不能为空" in response.json()["detail"]


class TestIntegration:
    """集成测试：完整流程"""
    
    def test_full_workflow(self, auth_token):
        """测试完整工作流：上传 -> 搜索 -> 删除"""
        # 1. 上传真实合同文件（实习合同 docx）
        assert REAL_CONTRACT_PATH.exists(), f"测试合同文件不存在: {REAL_CONTRACT_PATH}"

        with open(REAL_CONTRACT_PATH, "rb") as f:
            upload_response = client.post(
                "/api/documents/upload",
                headers={"Authorization": f"Bearer {auth_token}"},
                files={
                    "file": (
                        "internship1.docx",
                        f,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
        
        assert upload_response.status_code == 201
        contract_id = upload_response.json()["id"]
        
        # 2. 等待向量化完成
        import time
        time.sleep(3)
        
        # 3. 搜索
        search_response = client.post(
            "/api/search/by-contract",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                # 查询内容不依赖具体文案，只要能返回结果即可
                "query": "薪资待遇",
                "contract_id": contract_id,
                "top_k": 3
            }
        )
        
        assert search_response.status_code == 200
        search_data = search_response.json()
        assert search_data["total"] > 0
        
        # 4. 删除
        delete_response = client.delete(
            f"/api/documents/{contract_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert delete_response.status_code == 204


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

