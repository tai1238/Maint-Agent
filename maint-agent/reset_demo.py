# -*- coding: utf-8 -*-
"""演示状态一键重置：把系统还原到答辩演示的初始状态。

重置内容：
  1. 故障树图谱：移除回流并入的诱因（C_REFLOW_*），版本号固定回 1.2；
  2. 知识回流队列：只保留基准待审核案例 R-20261104-003（状态=待人工审核）；
  3. 维修台账：保留 3 条基准记录（两台历史 + R-20261104-003）；
  4. 演示日生成的工单与仿真日志流：清空。

用法：python reset_demo.py   （答辩/录屏前跑一次即可）
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

BASE = Path(__file__).parent
KG = BASE / "kg" / "fault_tree.json"
PENDING = BASE / "data" / "pending_kg_review.jsonl"
REPAIRS = BASE / "data" / "repair_log.json"
WORKORDERS = BASE / "data" / "workorders"
CNC_LOG = BASE / "data" / "cnc_log" / "vmc850_stream.log"

BASE_PENDING_ID = "R-20261104-003"
BASE_PENDING_LINE = (
    '{"record_id": "R-20261104-003", "device": "VMC850", '
    '"fault": "开机报伺服过载 X03（431/432），主轴转不动", '
    '"root_cause": "X 轴伺服动力线电柜侧接线端子松动并氧化，接触不良导致伺服过载报警", '
    '"action": "断电验电后检查 X 轴伺服动力线端子，打磨氧化层并重新紧固，上电后报警消除", '
    '"status": "待人工审核后并入故障树图谱"}'
)
BASE_REPAIR_IDS = {"R-2026-09-012", "R-2026-08-021", "R-20261104-003"}


def reset_kg():
    data = json.loads(KG.read_text(encoding="utf-8"))
    reflow = [cid for cid in data["causes"] if cid.startswith("C_REFLOW_")]
    for cid in reflow:
        data["causes"].pop(cid, None)
    for f in data["faults"].values():
        f["causes"] = [c for c in f["causes"] if not c.startswith("C_REFLOW_")]
    data["meta"]["version"] = "1.2"
    KG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"1. 图谱已重置：移除回流诱因 {len(reflow)} 条，版本固定 v1.2")


def reset_pending():
    PENDING.write_text(BASE_PENDING_LINE + "\n", encoding="utf-8")
    print(f"2. 回流队列已重置：仅保留基准待审核案例 {BASE_PENDING_ID}")


def reset_repairs():
    data = json.loads(REPAIRS.read_text(encoding="utf-8"))
    before = len(data["records"])
    data["records"] = [r for r in data["records"] if r["id"] in BASE_REPAIR_IDS]
    REPAIRS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"3. 维修台账已重置：{before} -> {len(data['records'])} 条（保留 3 条基准记录）")


def reset_workorders():
    n = 0
    if WORKORDERS.exists():
        for f in WORKORDERS.glob("WO-20261104-*.json"):
            f.unlink()
            n += 1
    print(f"4. 演示日工单已清理：删除 {n} 个")


def reset_cnc_log():
    CNC_LOG.parent.mkdir(parents=True, exist_ok=True)
    CNC_LOG.write_text("", encoding="utf-8")
    print("5. 仿真日志流已清空")


def main():
    reset_kg()
    reset_pending()
    reset_repairs()
    reset_workorders()
    reset_cnc_log()
    print("\n演示状态已就绪。启动演示：双击 start_demo.bat 或 python webapp.py")


if __name__ == "__main__":
    main()
