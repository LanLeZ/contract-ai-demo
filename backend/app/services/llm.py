import json
import logging
import os
import re
from typing import Any, Dict, List, Literal, Tuple

from dotenv import load_dotenv

try:
    from dashscope import Generation
    import dashscope
except ImportError:
    Generation = None
    dashscope = None


logger = logging.getLogger(__name__)

# 加载环境变量（使用默认 .env 位置，保持与项目其他模块一致）
load_dotenv()

ScopeType = Literal["contract_only", "contract_and_law"]


class QwenChatClient:
    """通义千问对话客户端封装"""

    def __init__(self, model: str = "qwen-plus") -> None:
        if Generation is None:
            raise ImportError("dashscope 未安装，请先运行: pip install dashscope")

        self.model = model
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("未找到 DASHSCOPE_API_KEY，请在 .env 中配置")

        # 与 test_llm.py 保持一致：直接设置全局 dashscope.api_key
        if dashscope is not None:
            dashscope.api_key = api_key

    def chat(self, messages: List[dict], temperature: float = 0.3) -> str:
        """
        调用通义千问进行对话

        Args:
            messages: [{"role": "system"|"user"|"assistant", "content": "..."}, ...]
        """
        resp = Generation.call(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )

        if resp.status_code != 200:
            logger.error("Qwen chat error: %s", resp.message)
            raise RuntimeError(f"Qwen chat 调用失败: {resp.message}")

        # DashScope Generation.call qwen-plus 当前返回 output["text"]
        return resp.output.get("text", "").strip()

    def analyze_scope_and_laws(self, question: str) -> Tuple[ScopeType, List[str]]:
        """
        一次性完成：检索范围分类 + 可能相关法律文件名抽取（贴近 Law-Book 的文件名风格）
        laws 输出示例：["民法典", "兵役法", "电子签名法"]
        """
        
        system_prompt = (
            "你是合同问答场景下的“检索意图分析助手”。\n"
            "任务：根据用户问题，判断是否需要检索通用法律条文，并（如需要）识别其直接提到或明显隐含需要适用的可能相关的法律名称。\n\n"
            "请严格输出 JSON（不要输出除 JSON 以外的任何文字）：\n"
            "{\n"
            "  \"scope\": \"contract_only\" | \"contract_and_law\",\n"
            "  \"laws\": [\"民法典\", \"兵役法（2021-08-20）\", \"电子签名法（2019-04-23）\"]\n"
            "}\n\n"
            "规则：\n"
            "- scope 只能二选一。\n"
            "- laws 里的每一项必须是“Law-Book 文件名风格”的简称：\n"
            "  - 不要加《》\n"
            "  - 不要带“中华人民共和国/中国”等前缀\n"
            "  - 不要带路径、不带扩展名 .md\n"
            "  - 日期（如（2021-08-20））可写可不写；不确定就不要编造日期\n"
            "- 若 scope=contract_only，则 laws 必须为空数组 []。\n"
            "- 若无法确定具体法律，但判断需要法律检索：scope=contract_and_law 且 laws=[]。\n"
        )
        user_prompt = f"用户问题：{question}"

        raw = self.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        ).strip()

        scope: ScopeType = "contract_only"
        laws: List[str] = []

        try:
            data = json.loads(raw)
            scope_raw = str(data.get("scope", "")).strip()
            if scope_raw in ("contract_only", "contract_and_law"):
                scope = scope_raw  # type: ignore[assignment]

            items = data.get("laws") or []
            if isinstance(items, list):
                laws = [str(x).strip() for x in items if str(x).strip()]
        except Exception:
            # 解析失败：直接退化为仅合同范围
            scope = "contract_only"
            return scope, []

        # 兜底清洗（防止模型偶尔输出《》/全称/扩展名）
        cleaned: List[str] = []
        for name in laws:
            x = name
            x = x.replace("《", "").replace("》", "")
            x = x.replace("中华人民共和国", "").replace("中国", "")
            x = x.replace(".md", "").replace(".markdown", "")
            x = x.strip()
            if x:
                cleaned.append(x)

        if scope == "contract_only":
            cleaned = []

        return scope, cleaned

    def answer_question_with_rag(
        self,
        question: str,
        contract_filename: str,
        scope: ScopeType,
        context_text: str,
        temperature: float = 0.3,
    ) -> str:
        """
        基于 RAG 上下文回答合同相关问题

        Args:
            question: 用户问题
            contract_filename: 合同文件名
            scope: 检索范围（contract_only 或 contract_and_law）
            context_text: 检索到的上下文（合同片段+法律条文）
            temperature: LLM 温度参数，默认 0.3

        Returns:
            LLM 生成的回答文本
        """
        system_prompt = (
            "你是一名精通中国合同与民商事法律的智能助手。\n"
            '你必须严格基于\"检索到的合同条款片段\"和\"检索到的法律条文片段\"来回答问题，'
            "优先引用这些片段中的关键信息进行分析与说明。\n"
            "如果上下文中没有足够信息支撑某个结论，请明确说明\"上下文未提供相关条款/法条，因此只能给出一般性提示\"，"
            "不要编造具体的条款号、法条内容或当事人名称。\n"
            "在回答中请尽量使用通俗易懂的中文，并在需要时给出实际操作建议（例如是否需要补充条款、修改条款或咨询律师）。"
        )

        user_prompt = (
            f"这是用户上传的一份合同：\n"
            f"- 文件名：{contract_filename}\n"
            f"- 问题检索范围：{scope}\n\n"
            f"以下是根据用户问题检索到的相关上下文（可能包括合同条款和法律条文）：\n\n"
            f"{context_text}\n\n"
            f"请你结合上述上下文，回答用户的问题：\n"
            f"{question}\n\n"
            "请注意：\n"
            '1. 优先引用给定片段中的信息进行分析，可以在表述中用\"根据检索到的第[编号]条片段\"来提示依据来源；\n'
            "2. 如果某个关键信息在上下文中找不到，请明确说明缺失，不要自行编造；\n"
            '3. 最后请用一两句话做\"综合风险总结\"和\"建议下一步怎么做\"。'
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        return self.chat(messages, temperature=temperature)


def _analyze_clauses_by_type(
    client: QwenChatClient,
    clauses: List[Dict[str, Any]],
    change_type: str,
    left_contract: Any,
    right_contract: Any,
) -> Dict[str, Dict[str, str]]:
    """
    按类型批量分析条款差异，返回 {clause_marker: {importance, explanation}} 的映射。
    
    Args:
        client: QwenChatClient 实例
        clauses: 同一类型的差异条款列表
        change_type: "delete" | "add" | "alter"
        left_contract: 左侧合同对象
        right_contract: 右侧合同对象
    
    Returns:
        {clause_marker: {"importance": "normal/vital", "explanation": "..."}}
    """
    if not clauses:
        return {}
    
    # 构建批量分析的 prompt
    if change_type == "delete":
        type_desc = "删除（该条款在左侧合同中存在，但在右侧合同中被删除）"
        clauses_text = "\n\n".join([
            f"条款编号：{c.get('clause_marker', '')}\n"
            f"被删除的条款内容：\n{c.get('left_text', '')}"
            for c in clauses
        ])
        user_prompt = (
            f"左侧合同文件名：{getattr(left_contract, 'filename', None)}\n"
            f"右侧合同文件名：{getattr(right_contract, 'filename', None)}\n\n"
            f"以下是多个被删除的条款（变更类型：{type_desc}）：\n\n"
            f"{clauses_text}\n\n"
            f"请为每个条款分析：\n"
            f"1. 该条款的重要性（importance）：normal（一般）或 vital（重要）\n"
            f"2. 删除该条款可能带来的风险或影响（explanation）：简要说明对乙方的潜在影响\n\n"
            f"请以 JSON 格式返回，格式如下（clause_marker 作为 key）：\n"
            f'{{\n'
            f'  "条款编号1": {{"importance": "normal/vital", "explanation": "风险说明"}},\n'
            f'  "条款编号2": {{"importance": "normal/vital", "explanation": "风险说明"}}\n'
            f'}}\n'
        )
    elif change_type == "add":
        type_desc = "新增（该条款在右侧合同中新增，左侧合同中没有）"
        clauses_text = "\n\n".join([
            f"条款编号：{c.get('clause_marker', '')}\n"
            f"新增的条款内容：\n{c.get('right_text', '')}"
            for c in clauses
        ])
        user_prompt = (
            f"左侧合同文件名：{getattr(left_contract, 'filename', None)}\n"
            f"右侧合同文件名：{getattr(right_contract, 'filename', None)}\n\n"
            f"以下是多个新增的条款（变更类型：{type_desc}）：\n\n"
            f"{clauses_text}\n\n"
            f"请为每个条款分析：\n"
            f"1. 该条款的重要性（importance）：normal（一般）或 vital（重要）\n"
            f"2. 新增该条款可能带来的风险或影响（explanation）：简要说明对乙方的潜在影响\n\n"
            f"请以 JSON 格式返回，格式如下（clause_marker 作为 key）：\n"
            f'{{\n'
            f'  "条款编号1": {{"importance": "normal/vital", "explanation": "风险说明"}},\n'
            f'  "条款编号2": {{"importance": "normal/vital", "explanation": "风险说明"}}\n'
            f'}}\n'
        )
    else:  # alter
        type_desc = "修改（该条款在两侧合同中都存在，但内容有差异）"
        clauses_text = "\n\n".join([
            f"条款编号：{c.get('clause_marker', '')}\n"
            f"左侧合同内容：\n{c.get('left_text', '')}\n\n"
            f"右侧合同内容：\n{c.get('right_text', '')}"
            for c in clauses
        ])
        user_prompt = (
            f"左侧合同文件名：{getattr(left_contract, 'filename', None)}\n"
            f"右侧合同文件名：{getattr(right_contract, 'filename', None)}\n\n"
            f"以下是多个被修改的条款（变更类型：{type_desc}）：\n\n"
            f"{clauses_text}\n\n"
            f"请为每个条款分析，首先判断差异是否存在实质性差异：\n\n"
            f"【实质性差异判断标准】\n"
            f"- 如果只是同义词替换或表达方式变化（如\"工资\"改为\"报酬\"、\"甲方\"改为\"委托方\"），"
            f"  没有改变权利义务关系、支付方式、时间地点等关键要素，则属于 normal（一般）级别。\n"
            f"- 如果改变了权利义务关系、支付方式、时间地点、责任范围等关键要素"
            f"  （如\"转账\"改为\"现金支付\"、\"30天\"改为\"60天\"、\"不可抗力\"改为\"可抗力\"），"
            f"  则属于 vital（重要）级别。\n\n"
            f"请为每个条款输出：\n"
            f"1. 该条款的重要性（importance）：normal（一般）或 vital（重要）\n"
            f"   - 请先判断是否存在实质性差异，再确定 importance 级别\n"
            f"2. 内容修改可能带来的风险或影响（explanation）：简要说明对乙方的潜在影响\n\n"
            f"请以 JSON 格式返回，格式如下（clause_marker 作为 key）：\n"
            f'{{\n'
            f'  "条款编号1": {{"importance": "normal/vital", "explanation": "风险说明"}},\n'
            f'  "条款编号2": {{"importance": "normal/vital", "explanation": "风险说明"}}\n'
            f'}}\n'
        )
    
    system_prompt = (
        "你是一名精通中国合同与民商事法律的合同对比与风险分析助手。\n"
        "请分析多个合同条款的差异，首先判断差异是否存在实质性差异，然后评估每个条款的重要性并给出风险提示。\n"
        "请用中文输出，语言简洁专业。必须严格按照要求的 JSON 格式返回。"
    )
    
    try:
        response = client.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        
        # 解析 JSON 响应
        if response:
            # 尝试提取 JSON 部分
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    # 验证并转换格式
                    result = {}
                    for marker, analysis in parsed.items():
                        if isinstance(analysis, dict):
                            result[str(marker)] = {
                                "importance": analysis.get("importance", "normal"),
                                "explanation": analysis.get("explanation", ""),
                            }
                        elif isinstance(analysis, str):
                            # 如果直接是字符串，尝试解析
                            result[str(marker)] = {
                                "importance": "normal",
                                "explanation": analysis,
                            }
                    return result
                except json.JSONDecodeError:
                    logger.warning(f"解析 {change_type} 类型条款的 LLM 响应 JSON 失败: {response[:200]}")
    except Exception:
        logger.exception(f"批量分析 {change_type} 类型条款失败")
    
    # 解析失败，返回默认值
    return {c.get("clause_marker", ""): {"importance": "normal", "explanation": ""} for c in clauses}


def attach_contract_compare_llm_analysis(
    base_result: Dict[str, Any],
    left_contract: Any,
    right_contract: Any,
) -> None:
    """
    合同对比场景下的统一 LLM 差异分析入口。
    
    优化：按 change_type 分类批量调用 LLM，而不是为每个条款单独调用。
    为每个差异条款生成 importance 和 explanation。

    说明：
    - 仅依赖于 QwenChatClient，不直接依赖 SQLAlchemy 模型类型，避免循环导入；
    - 调用失败（包括 dashscope 未安装 / API Key 缺失 / LLM 报错）时会静默降级，不影响基础对比结果。
    """
    try:
        client = QwenChatClient()
    except Exception:
        logger.exception("初始化 QwenChatClient 失败，跳过合同差异 LLM 分析")
        return

    # 使用 all_differences（新格式，由 contract_compare.py 统一生成）
    all_differences: List[Dict[str, Any]] = base_result.get("all_differences", [])
    
    if not all_differences:
        logger.info("没有差异条款需要分析")
        return
    
    # 按 change_type 分类，并过滤掉没有文本内容的条款（这些条款无法进行有效分析）
    clauses_by_type: Dict[str, List[Dict[str, Any]]] = {
        "delete": [],
        "add": [],
        "alter": [],
    }
    
    # 记录没有文本的条款，直接给默认值
    clauses_without_text: List[Dict[str, Any]] = []
    
    for clause_data in all_differences:
        change_type = clause_data.get("change_type", "alter")
        
        # 检查是否有文本内容
        if change_type == "delete":
            has_text = bool(clause_data.get("left_text", "").strip())
        elif change_type == "add":
            has_text = bool(clause_data.get("right_text", "").strip())
        else:  # alter
            has_text = bool(clause_data.get("left_text", "").strip()) or bool(clause_data.get("right_text", "").strip())
        
        if has_text and change_type in clauses_by_type:
            clauses_by_type[change_type].append(clause_data)
        else:
            # 没有文本的条款，直接给默认值
            clauses_without_text.append(clause_data)
    
    # 为没有文本的条款设置默认值
    all_analysis_results: Dict[str, Dict[str, str]] = {}
    for clause in clauses_without_text:
        marker = clause.get("clause_marker", "")
        all_analysis_results[marker] = {
            "importance": "normal",
            "explanation": "该条款缺少文本内容，无法进行详细分析。",
        }
    
    # 按类型批量调用 LLM（只分析有文本内容的条款）
    for change_type, clauses in clauses_by_type.items():
        if not clauses:
            continue
        
        try:
            analysis_results = _analyze_clauses_by_type(
                client=client,
                clauses=clauses,
                change_type=change_type,
                left_contract=left_contract,
                right_contract=right_contract,
            )
            all_analysis_results.update(analysis_results)
        except Exception:
            logger.exception(f"批量分析 {change_type} 类型条款失败，使用默认值")
            # 为失败的条款设置默认值
            for clause in clauses:
                marker = clause.get("clause_marker", "")
                if marker not in all_analysis_results:
                    all_analysis_results[marker] = {"importance": "normal", "explanation": ""}
    
    # 将分析结果合并到条款数据中
    for clause_data in all_differences:
        marker = clause_data.get("clause_marker", "")
        analysis = all_analysis_results.get(marker, {})
        clause_data["importance"] = analysis.get("importance", "normal")
        clause_data["explanation"] = analysis.get("explanation", "")
    
    # 更新 base_result，将分析结果写回原始数据结构
    base_result["all_differences"] = all_differences
    
    # 更新 only_in_left（字典列表格式）
    only_in_left = base_result.get("only_in_left", [])
    if isinstance(only_in_left, list):
        for clause in only_in_left:
            if isinstance(clause, dict):
                marker = clause.get("clause_marker", "")
                analysis = all_analysis_results.get(marker, {})
                clause["importance"] = analysis.get("importance", "normal")
                clause["explanation"] = analysis.get("explanation", "")
    
    # 更新 only_in_right（字典列表格式）
    only_in_right = base_result.get("only_in_right", [])
    if isinstance(only_in_right, list):
        for clause in only_in_right:
            if isinstance(clause, dict):
                marker = clause.get("clause_marker", "")
                analysis = all_analysis_results.get(marker, {})
                clause["importance"] = analysis.get("importance", "normal")
                clause["explanation"] = analysis.get("explanation", "")
    
    # 更新 changed_clauses，为它们添加 importance 和 explanation
    changed_clauses = base_result.get("changed_clauses", [])
    if isinstance(changed_clauses, list):
        for changed_clause in changed_clauses:
            if isinstance(changed_clause, dict):
                marker = changed_clause.get("clause_marker", "")
                analysis = all_analysis_results.get(marker, {})
                changed_clause["importance"] = analysis.get("importance", "normal")
                changed_clause["explanation"] = analysis.get("explanation", "")


