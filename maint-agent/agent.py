# -*- coding: utf-8 -*-
"""Maint-Agent 核心：DeepSeek Function Calling 任务调度主循环。

流程：用户输入 -> 模型规划与工具调用（可多轮）-> 汇总生成工人可读的回复。
系统提示词内置工业风控约束：优先故障树、不确定不妄断、高危提醒、严禁编造。
"""
import os
import time
from pathlib import Path

from openai import OpenAI

from kg.graph import FaultTree
from rag.retriever import BM25Retriever
from tools import TOOLS_SCHEMA, dispatch

BASE_DIR = Path(__file__).parent

SYSTEM_PROMPT = """你是"Maint-Agent"，面向中小机加工工厂的设备维保智能体，服务对象是车间维修师傅和设备管理员。

你的工作方式：
1. 收到故障描述后，先调用 match_fault 识别设备与故障类型，再调用 get_causes 获取故障树排查链路（已按"由简到繁"排序），并调用 search_docs 检索手册与历史维修记录。
2. 给师傅的排查指引必须按顺序列出步骤，用车间师傅能听懂的通俗语言，一次只让师傅做当前这一步，等他反馈结果再进行下一步。
3. 可能涉及更换备件时，调用 query_parts 查库存；故障确认需要正式处理时，调用 create_workorder 生成工单。
4. 师傅反馈"已修好"后，调用 log_repair 把维修路径入库。
5. 管理员问统计（本月最高发故障、停机时长等）时，调用 monthly_stats。

工业风控铁律（必须遵守）：
- 排查结论必须来自故障树或检索到的文档，没有可靠依据时明确说明"不确定"，绝不编造配件型号、参数数值、检修方案；
- 涉及带电操作、参数修改、主轴大修等高危动作时必须给出风险提醒，并建议联系厂家工程师；
- 回复中不要堆砌专业术语，优先说人话。"""

# 供 Agent 使用的知识库查询工具（本地函数，不走大模型）
KG_QUERIES_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "match_fault",
            "description": "在故障树知识图谱中按报警码或故障现象匹配故障节点",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "包含报警码或故障现象的原文"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_causes",
            "description": "获取指定故障的诱因排查链路，已按由简到繁排序（成本低、风险低的排前面）",
            "parameters": {
                "type": "object",
                "properties": {
                    "fault_id": {"type": "string", "description": "故障节点ID，来自 match_fault 返回结果"},
                },
                "required": ["fault_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": "在手册与历史维修记录文档库中检索相关内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索关键词或问题"},
                },
                "required": ["query"],
            },
        },
    },
]


class MaintAgent:
    def __init__(self, api_key: str | None = None, model: str = "deepseek-chat"):
        key = api_key or _load_api_key()
        if not key:
            raise RuntimeError(
                "未找到 DeepSeek API Key。请设置环境变量 DEEPSEEK_API_KEY，"
                "或在 maint-agent/.env 文件中写入 DEEPSEEK_API_KEY=sk-xxx"
            )
        self.client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
        self.model = model
        self.kg = FaultTree()
        self.retriever = BM25Retriever()
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        # 本地知识查询工具与业务工具合并注册
        self.local_tools = {
            "match_fault": self._match_fault,
            "get_causes": self._get_causes,
            "search_docs": self._search_docs,
        }
        self.all_schemas = KG_QUERIES_SCHEMA + TOOLS_SCHEMA
        self.trace: list[str] = []   # 工具调用轨迹，供演示展示

    # ---------- 本地知识查询 ----------

    def _match_fault(self, text: str) -> str:
        fault = self.kg.match_fault(text)
        if not fault:
            known = "；".join(f"{f['name']}（报警码 {'/'.join(f['alarm_codes'])}）" for f in self.kg.list_faults())
            return f"故障树中未匹配到该故障。当前图谱覆盖的故障有：{known}。建议切换 RAG 检索并提示管理员补充图谱。"
        return json_dumps(fault)

    def _get_causes(self, fault_id: str) -> str:
        causes = self.kg.ranked_causes(fault_id)
        if not causes:
            return f"图谱中不存在故障 {fault_id}"
        return json_dumps(causes)

    def _search_docs(self, query: str) -> str:
        hits = self.retriever.search(query, top_k=3)
        if not hits:
            return "文档库中未检索到相关内容。"
        return json_dumps([
            {"来源": h["doc"], "相关度": h["score"], "内容摘录": h["text"][:400]}
            for h in hits
        ])

    # ---------- 主循环 ----------

    def _call_llm(self):
        """调用 DeepSeek，网络抖动/超时自动重试（演示现场容错）。"""
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    tools=self.all_schemas,
                    temperature=0.3,
                    timeout=60,
                )
            except Exception as e:  # noqa: BLE001 - 网络类异常统一重试
                last_err = e
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"大模型调用失败（已重试 3 次）：{last_err}") from last_err

    def chat(self, user_input: str, max_rounds: int = 8) -> str:
        self.messages.append({"role": "user", "content": user_input})
        for _ in range(max_rounds):
            resp = self._call_llm()
            msg = resp.choices[0].message

            if not msg.tool_calls:
                self.messages.append({"role": "assistant", "content": msg.content})
                return msg.content

            self.messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
            })
            for tc in msg.tool_calls:
                import json
                name = tc.function.name
                args = json.loads(tc.function.arguments or "{}")
                self.trace.append(f"{name}({args})")
                if name in self.local_tools:
                    result = self.local_tools[name](**args)
                else:
                    result = dispatch(name, args)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
        return "（已达单次任务最大工具调用轮数，请换个问法或直接联系管理员）"


def _load_api_key() -> str | None:
    """优先环境变量，其次项目根目录 .env 文件。"""
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DEEPSEEK_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None


def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)
