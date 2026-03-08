"""
API接口测试脚本
使用方法: python test_api.py
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_register():
    """测试用户注册"""
    print("\n=== 测试用户注册 ===")
    register_data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123"
    }
    try:
        response = requests.post(f"{BASE_URL}/api/auth/register", json=register_data)
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 201
    except Exception as e:
        print(f"错误: {e}")
        return False

def test_login():
    """测试用户登录"""
    print("\n=== 测试用户登录 ===")
    login_data = {
        "username": "testuser",
        "password": "password123"
    }
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data=login_data
        )
        print(f"状态码: {response.status_code}")
        result = response.json()
        print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
        if response.status_code == 200:
            return result.get("access_token")
        return None
    except Exception as e:
        print(f"错误: {e}")
        return None

def test_get_user_info(token):
    """测试获取用户信息"""
    print("\n=== 测试获取用户信息 ===")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"错误: {e}")
        return False

def test_health_check():
    """测试健康检查"""
    print("\n=== 测试健康检查 ===")
    try:
        response = requests.get(f"{BASE_URL}/api/health")
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"错误: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("合同智能解读系统 - API接口测试")
    print("=" * 50)
    
    # 测试健康检查
    if not test_health_check():
        print("\n❌ 后端服务未启动，请先启动后端服务")
        exit(1)
    
    # 测试注册（如果用户已存在会失败，这是正常的）
    test_register()
    
    # 测试登录
    token = test_login()
    if not token:
        print("\n❌ 登录失败，请检查用户名和密码")
        exit(1)
    
    # 测试获取用户信息
    if test_get_user_info(token):
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 获取用户信息失败")































