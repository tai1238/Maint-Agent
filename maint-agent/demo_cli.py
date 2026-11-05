# -*- coding: utf-8 -*-
"""Maint-Agent 演示命令行。

用法：
    python demo_cli.py            # 交互对话
    python demo_cli.py --selftest # 不调大模型，仅自测知识库与工具层
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

BANNER = """
============================================================
   Maint-Agent · 中小型机加工设备维保智能体（演示版）
   试一试：
   1) 这台 VMC850 开机就报伺服过载，主轴转不动，昨天还正常
   2) 报了506润滑压力异常怎么回事
   3) 修好了，是接线松了，花了大概1个小时
   4) 本月三台设备最高发的故障是什么
   输入 q 退出
============================================================
"""


def selftest() -> bool:
    """不依赖 API Key，验证图谱推理、RAG 检索、工具分发三条链路。"""
    from kg.graph import FaultTree
    from rag.retriever import BM25Retriever
    from tools import dispatch

    print("== 自测 1：故障树匹配（报警码 431 + 现象描述） ==")
    kg = FaultTree()
    fault = kg.match_fault("VMC850 开机报伺服过载，X03，主轴转不动")
    assert fault, "故障匹配失败"
    print(f"匹配到：{fault['name']}（{fault['id']}），严重度 {fault['severity']}")

    print("\n== 自测 2：由简到繁诱因排序 ==")
    for i, c in enumerate(kg.ranked_causes(fault["id"]), 1):
        print(f"{i}. {c['name']}｜成本{c['cost']}｜风险{c['risk']}｜先验{c['prob']}")
    costs = [c["cost"] for c in kg.ranked_causes(fault["id"])]
    assert costs == sorted(costs, key={"低": 0, "中": 1, "高": 2}.get), "排序不符合由简到繁"

    print("\n== 自测 3：RAG 检索历史同类案例 ==")
    hits = BM25Retriever().search("VMC850 伺服过载 上次怎么修好的", top_k=2)
    for h in hits:
        print(f"[{h['doc']} score={h['score']}] {h['text'][:60].replace(chr(10), ' ')}...")
    assert hits, "RAG 检索无结果"

    print("\n== 自测 4：备件查询 / 月度统计 ==")
    print(dispatch("query_parts", {"keyword": "伺服"}))
    print(dispatch("monthly_stats", {}))

    print("\n== 自测 5：知识回流合并（内存模拟，不写盘） ==")
    before = len(kg.faults["F_SERVO_OVERLOAD"]["causes"])
    cid = kg.add_cause(
        "F_SERVO_OVERLOAD",
        name="测试回流诱因（自测）",
        check_steps=["示例步骤 1", "示例步骤 2"],
        source="SELFTEST",
    )
    after = len(kg.faults["F_SERVO_OVERLOAD"]["causes"])
    assert after == before + 1, "回流合并后诱因数量未增加"
    cid2 = kg.add_cause("F_SERVO_OVERLOAD", name="测试回流诱因（自测）", check_steps=["x"])
    assert cid2 == cid, "同名诱因未去重"
    costs = [c["cost"] for c in kg.ranked_causes("F_SERVO_OVERLOAD")]
    assert costs == sorted(costs, key={"低": 0, "中": 1, "高": 2}.get), "合并后排序被破坏"
    print(f"新诱因 {cid} 已入链路，同名去重通过，由简到繁排序保持正确")

    print("\n== 自测 6：待审核队列可读 ==")
    pending_path = Path(__file__).parent / "data" / "pending_kg_review.jsonl"
    n = 0
    if pending_path.exists():
        n = sum(1 for line in pending_path.read_text(encoding="utf-8").splitlines() if line.strip())
    print(f"待审核队列文件可解析，当前 {n} 条记录（python kg_review.py list 查看）")

    print("\n== 自测 7：跨设备型号匹配 ==")
    f = kg.match_fault("VMC650 加工的件尺寸老是不稳定，漂移超差了")
    assert f and f.get("device") == "VMC650", "VMC650 尺寸漂移未命中"
    print(f"命中：{f['name']}（{f['device']}），{len(f['causes'])} 类诱因，跨型号平移验证通过")

    print("\n全部自测通过。运行 python demo_cli.py 进入完整对话演示。")
    return True


def main():
    if "--selftest" in sys.argv:
        selftest()
        return

    from agent import MaintAgent

    print(BANNER)
    agent = MaintAgent()
    while True:
        try:
            user = input("\n师傅> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见")
            break
        if not user:
            continue
        if user.lower() in ("q", "quit", "exit"):
            break
        agent.trace.clear()
        print("\nMaint-Agent> ", end="", flush=True)
        reply = agent.chat(user)
        print(reply)
        if agent.trace:
            print(f"\n[工具调用轨迹] {' -> '.join(agent.trace)}")


if __name__ == "__main__":
    main()
