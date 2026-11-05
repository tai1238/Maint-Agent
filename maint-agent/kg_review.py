# -*- coding: utf-8 -*-
"""知识回流审核台：把"待审核队列"里的维修案例并入故障树图谱。

闭环最后一环：维修入库 -> pending_kg_review.jsonl ->（本工具人工审核）-> 图谱新知识。

用法：
    python kg_review.py list                 # 查看待审核案例
    python kg_review.py approve <record_id>  # 审核通过，并入图谱
    python kg_review.py discard <record_id>  # 驳回（不并入图谱）
    python kg_review.py demo                 # 演示模式：自动审核第一条演示案例
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from kg.graph import FaultTree  # noqa: E402
from tools import PENDING_REVIEW  # noqa: E402

STATUS_PENDING = "待人工审核后并入故障树图谱"
STATUS_MERGED = "已审核通过并入图谱"


def _read_queue() -> list[dict]:
    if not PENDING_REVIEW.exists():
        return []
    items = []
    for line in PENDING_REVIEW.read_text(encoding="utf-8").splitlines():
        if line.strip():
            items.append(json.loads(line))
    return items


def _write_queue(items: list[dict]):
    with open(PENDING_REVIEW, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def list_pending() -> str:
    items = [it for it in _read_queue() if it.get("status") == STATUS_PENDING]
    if not items:
        return "待审核队列为空。"
    lines = [f"共 {len(items)} 条待审核："]
    for it in items:
        lines.append(
            f"- [{it['record_id']}] {it['device']}｜{it['fault']}\n"
            f"  根因：{it['root_cause']}\n"
            f"  处置：{it['action']}"
        )
    return "\n".join(lines)


def _set_status(record_id: str, status: str) -> bool:
    items = _read_queue()
    hit = False
    for it in items:
        if it["record_id"] == record_id:
            it["status"] = status
            hit = True
    if hit:
        _write_queue(items)
    return hit


def approve(record_id: str, fault_id: str = "F_SERVO_OVERLOAD") -> str:
    """审核通过：案例根因并入故障树，成为新诱因节点（同名去重）。"""
    items = _read_queue()
    target = next((it for it in items if it["record_id"] == record_id), None)
    if not target:
        return f"未找到记录 {record_id}，请先 python kg_review.py list 查看。"
    if target.get("status") == STATUS_MERGED:
        return f"记录 {record_id} 已并入图谱，无需重复审核。"

    kg = FaultTree()
    steps = [s.strip() for s in target["action"].replace("；", "；\n").split("\n") if s.strip()]
    cid = kg.add_cause(fault_id, name=target["root_cause"], check_steps=steps, source=record_id)
    kg.save()
    _set_status(record_id, STATUS_MERGED)
    return (
        f"已并入图谱：{record_id} -> {fault_id} / {cid}\n"
        f"图谱版本升至 {FaultTree().data['meta']['version']}，"
        f"该故障的诱因排查链路已实时更新。"
    )


def discard(record_id: str) -> str:
    if _set_status(record_id, "已驳回（不并入图谱）"):
        return f"已驳回 {record_id}，该案例保留在台账但不会进入图谱。"
    return f"未找到记录 {record_id}。"


def demo():
    """演示模式：把队列里第一条待审核案例自动审核通过，展示回流效果。"""
    pending = [it for it in _read_queue() if it.get("status") == STATUS_PENDING]
    if not pending:
        print("当前无待审核案例。可先在对话里报修并反馈'已修好'生成一条。")
        return
    it = pending[0]
    print("== 审核前：该故障的诱因链路 ==")
    kg = FaultTree()
    for i, c in enumerate(kg.ranked_causes("F_SERVO_OVERLOAD"), 1):
        print(f"{i}. {c['name']}｜成本{c['cost']}｜风险{c['risk']}")
    print(f"\n== 审核通过：{it['record_id']} ==")
    print(approve(it["record_id"]))
    print("\n== 审核后：诱因链路（自动加入由简到繁排序） ==")
    for i, c in enumerate(FaultTree().ranked_causes("F_SERVO_OVERLOAD"), 1):
        print(f"{i}. {c['name']}｜成本{c['cost']}｜风险{c['risk']}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        print(list_pending())
    elif cmd == "approve":
        print(approve(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "F_SERVO_OVERLOAD"))
    elif cmd == "discard":
        print(discard(sys.argv[2]))
    elif cmd == "demo":
        demo()
    else:
        print(__doc__)
