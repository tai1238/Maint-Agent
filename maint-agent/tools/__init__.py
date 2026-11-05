# -*- coding: utf-8 -*-
"""工具集：工单生成 / 备件查询 / 维修入库 / 月度统计。

每个工具同时提供：
- 可执行函数（本地读写 JSON / 文件）
- OpenAI Function Calling 的 JSON Schema（供 Agent 声明）
"""
import json
import re
from datetime import date, datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
WORKORDER_DIR = DATA_DIR / "workorders"
REPAIR_LOG = DATA_DIR / "repair_log.json"
PARTS_INVENTORY = DATA_DIR / "parts_inventory.json"
PENDING_REVIEW = DATA_DIR / "pending_kg_review.jsonl"   # 待人工审核入图谱的案例


# ---------- 1. 工单生成 ----------

def create_workorder(device: str, fault_desc: str, suspected_cause: str,
                     priority: str = "中", parts_needed: list[str] | None = None) -> str:
    """生成标准化维保工单，写入 workorders 目录。"""
    WORKORDER_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().strftime("%Y%m%d")
    existing = list(WORKORDER_DIR.glob(f"WO-{today}-*.json"))
    wo_no = f"WO-{today}-{len(existing) + 1:03d}"
    order = {
        "工单号": wo_no,
        "创建时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "设备": device,
        "故障描述": fault_desc,
        "初步判断原因": suspected_cause,
        "优先级": priority,
        "所需备件": parts_needed or [],
        "状态": "待处理",
    }
    path = WORKORDER_DIR / f"{wo_no}.json"
    path.write_text(json.dumps(order, ensure_ascii=False, indent=2), encoding="utf-8")
    return f"工单已生成：{wo_no}（优先级 {priority}），已保存到 {path.name}"


# ---------- 2. 备件查询 ----------

def query_parts(keyword: str) -> str:
    """按名称/型号关键词查询备件库存。"""
    inventory = json.loads(PARTS_INVENTORY.read_text(encoding="utf-8"))
    hits = [
        p for p in inventory["parts"]
        if keyword in p["name"] or keyword in p["model"] or keyword in p["id"]
    ]
    if not hits:
        # 宽松一点：任一字符命中也算
        hits = [p for p in inventory["parts"] if any(ch in p["name"] + p["model"] for ch in keyword)]
    if not hits:
        return f"备件库中未找到与「{keyword}」相关的备件。"
    lines = []
    for p in hits:
        stock = f"库存 {p['stock']} 件" if p["stock"] > 0 else "无库存，需采购"
        lines.append(f"- {p['name']}（{p['model']}）：{stock}，位置 {p['location']}，{p['price_note']}")
    return "备件查询结果：\n" + "\n".join(lines)


# ---------- 3. 维修记录入库 ----------

def log_repair(device: str, fault_desc: str, root_cause: str,
               action_taken: str, downtime_minutes: int) -> str:
    """维修确认后入库：写台账 + 加入图谱待审核队列（知识自回流）。"""
    log = json.loads(REPAIR_LOG.read_text(encoding="utf-8"))
    today = date.today().strftime("%Y-%m-%d")
    seq = len(log["records"]) + 1
    rid = f"R-{today.replace('-', '')}-{seq:03d}"
    log["records"].append({
        "id": rid, "date": today, "device": device, "fault": fault_desc,
        "root_cause": root_cause, "action": action_taken,
        "downtime_minutes": downtime_minutes,
    })
    REPAIR_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

    with open(PENDING_REVIEW, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "record_id": rid, "device": device, "fault": fault_desc,
            "root_cause": root_cause, "action": action_taken,
            "status": "待人工审核后并入故障树图谱",
        }, ensure_ascii=False) + "\n")
    return f"维修记录已入库：{rid}；该案例已加入知识图谱待审核队列，供管理员确认后沉淀为图谱知识。"


# ---------- 4. 月度统计 ----------

def monthly_stats(month: str = "") -> str:
    """统计指定月份（默认当月）的维修记录：最高发故障、停机总时长。"""
    log = json.loads(REPAIR_LOG.read_text(encoding="utf-8"))
    month = month or date.today().strftime("%Y-%m")
    records = [r for r in log["records"] if r["date"].startswith(month)]
    if not records:
        return f"{month}暂无维修记录。"
    fault_count: dict[str, int] = {}
    for r in records:
        key = _fault_key(r["fault"])
        fault_count[key] = fault_count.get(key, 0) + 1
    top = sorted(fault_count.items(), key=lambda x: -x[1])
    total_downtime = sum(r["downtime_minutes"] for r in records)
    lines = [f"{month} 维保统计：共 {len(records)} 次维修，停机总计 {total_downtime} 分钟（{total_downtime / 60:.1f} 小时）。", "最高发故障："]
    for i, (fault, cnt) in enumerate(top[:3], 1):
        lines.append(f"{i}. {fault}：{cnt} 次")
    return "\n".join(lines)


def _fault_key(fault: str) -> str:
    """把故障描述归并为统计口径，去掉具体轴/序号细节。"""
    for kw in ("过载", "润滑", "过热", "报警"):
        if kw in fault:
            return kw
    return fault[:12]


# ---------- Function Calling Schema ----------

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "create_workorder",
            "description": "生成标准化维保工单。当故障确认需要正式处理、涉及备件采购或高危作业时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {"type": "string", "description": "设备型号，如 VMC850"},
                    "fault_desc": {"type": "string", "description": "故障描述"},
                    "suspected_cause": {"type": "string", "description": "初步判断的原因"},
                    "priority": {"type": "string", "enum": ["高", "中", "低"], "description": "工单优先级"},
                    "parts_needed": {"type": "array", "items": {"type": "string"}, "description": "所需备件名称列表"},
                },
                "required": ["device", "fault_desc", "suspected_cause"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_parts",
            "description": "查询备件库存。当排查方案中可能需要更换零件、或师傅询问配件是否有货时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "备件名称或型号关键词，如：伺服驱动器、轴承、润滑油"},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_repair",
            "description": "故障修复确认后，把本次维修路径写入台账，并加入知识图谱待审核队列。仅在用户明确反馈已修好后调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {"type": "string", "description": "设备型号"},
                    "fault_desc": {"type": "string", "description": "故障描述"},
                    "root_cause": {"type": "string", "description": "最终确认的根本原因"},
                    "action_taken": {"type": "string", "description": "采取的维修动作"},
                    "downtime_minutes": {"type": "integer", "description": "本次停机分钟数，未知填 0"},
                },
                "required": ["device", "fault_desc", "root_cause", "action_taken"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "monthly_stats",
            "description": "统计某月维修次数、最高发故障和停机总时长。管理员做复盘提问时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "string", "description": "月份，格式 YYYY-MM，留空表示当月"},
                },
            },
        },
    },
]


TOOL_IMPLS = {
    "create_workorder": create_workorder,
    "query_parts": query_parts,
    "log_repair": log_repair,
    "monthly_stats": monthly_stats,
}


def dispatch(name: str, args: dict) -> str:
    """统一工具分发入口，兜住参数异常避免 Agent 循环中断。"""
    impl = TOOL_IMPLS.get(name)
    if not impl:
        return f"未知工具：{name}"
    try:
        return str(impl(**args))
    except TypeError as e:
        return f"工具 {name} 参数错误：{e}"
    except Exception as e:  # noqa: BLE001 - 工具层兜底，错误信息回传给模型自行修正
        return f"工具 {name} 执行失败：{e}"
