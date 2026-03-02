# 测试脚本 test_torch.py
try:
    import torch
    print(f"✅ PyTorch 版本: {torch.__version__}")
    print(f"✅ PyTorch 安装路径: {torch.__file__}")
    
    # 测试基本功能
    x = torch.tensor([1.0, 2.0, 3.0])
    print(f"✅ 张量创建成功: {x}")
    
    # CPU 在 PyTorch 中总是可用的，不需要检查
    print(f"✅ CPU 可用: True（PyTorch CPU 版本默认可用）")
    
    # 检查 CUDA (GPU) 是否可用（可选）
    print(f"ℹ️  CUDA (GPU) 可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"   CUDA 设备数量: {torch.cuda.device_count()}")
        print(f"   当前 CUDA 设备: {torch.cuda.get_device_name(0)}")
    else:
        print(f"   （这是正常的，你安装的是 CPU 版本）")
    
    # 检查设备信息
    print(f"✅ 默认设备: {x.device}")
    
except Exception as e:
    print(f"❌ PyTorch 导入失败: {e}")
    import traceback
    traceback.print_exc()