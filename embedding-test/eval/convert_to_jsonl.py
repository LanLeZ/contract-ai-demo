import json

# 读取文件
with open('queries.jsonl', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 解析对象
objects = []
current_obj = []
in_object = False

for line in lines:
    stripped = line.strip()
    
    # 跳过空行和方括号
    if not stripped or stripped in ['[', ']']:
        continue
    
    # 开始新对象
    if stripped.startswith('{'):
        if current_obj:
            # 解析之前的对象
            obj_str = ' '.join(current_obj).replace('    ', ' ')
            try:
                obj = json.loads(obj_str)
                objects.append(obj)
            except:
                pass
        current_obj = [stripped]
        in_object = True
    elif in_object:
        # 移除末尾的逗号
        if stripped.endswith(','):
            stripped = stripped[:-1]
        current_obj.append(stripped)
        
        # 对象结束
        if stripped.endswith('}'):
            obj_str = ' '.join(current_obj)
            try:
                obj = json.loads(obj_str)
                objects.append(obj)
            except:
                pass
            current_obj = []
            in_object = False

# 处理最后一个对象
if current_obj:
    obj_str = ' '.join(current_obj)
    try:
        obj = json.loads(obj_str)
        objects.append(obj)
    except:
        pass

# 写入 JSONL 格式
with open('queries.jsonl', 'w', encoding='utf-8') as f:
    for obj in objects:
        f.write(json.dumps(obj, ensure_ascii=False) + '\n')

print(f'转换完成，共 {len(objects)} 个对象')



















