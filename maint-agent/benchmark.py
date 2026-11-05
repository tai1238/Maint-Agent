# -*- coding: utf-8 -*-
"""量化对比实测：人工翻手册排查 vs Agent 引导排查。

产出可复现的真实数字（不编造）：
- 人工基线：基于语料结构的可数事实（跨文档数、查找动作数、需读字符数），耗时按
  平均阅读速度折算并标注估算方法；
- Agent 路径：真实调用 DeepSeek 计时（报修 -> 排查指引 / 反馈修复 -> 入库回流）。

运行：python benchmark.py   （需要 .env 中有效的 DEEPSEEK_API_KEY）
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

BASE = Path(__file__).parent
CORPUS = BASE / "rag" / "corpus"
READ_SPEED = 300          # 字/分钟，中文 average 阅读速度
LOOKUP_PER_DOC = 20       # 秒/份，在一份文档中定位相关章节的平均翻找耗时（估算）

OUT = BASE / "data" / "benchmark_result.json"


def corpus_stats() -> dict:
    stats = {}
    for f in sorted(CORPUS.glob("*.txt")):
        text = f.read_text(encoding="utf-8")
        stats[f.name] = {
            "chars": len(re.sub(r"\s", "", text)),
            "lines": len([l for l in text.splitlines() if l.strip()]),
        }
    records = len(re.findall(r"【记录", (CORPUS / "repair_history.txt").read_text(encoding="utf-8")))
    return {"files": stats, "repair_records": records,
            "total_chars": sum(s["chars"] for s in stats.values())}


def manual_baseline() -> dict:
    """人工基线：师傅只知道报警码 X03，仅靠纸质/文档资料排查。

    流程每一步都对应语料中可验证的结构，数字由 corpus_stats 统计得出。
    """
    st = corpus_stats()
    manual = st["files"]["manual_alarm_codes.txt"]["chars"]
    maint = st["files"]["vmc850_maintenance.txt"]["chars"]
    history = st["files"]["repair_history.txt"]["chars"]
    n_records = st["repair_records"]
    steps = [
        {"动作": "在报警手册中定位 431/X03 条目", "需读": f"通读手册全文 {manual} 字"},
        {"动作": "发现手册只给方向，无本厂诱因链与备件对应", "需读": "转下一份文档"},
        {"动作": "在保养规范中找相关点检项", "需读": f"通读保养规范 {maint} 字"},
        {"动作": f"在维修台账中逐条找同类案例（共 {n_records} 条）", "需读": f"通读台账 {history} 字"},
    ]
    read_chars = manual + maint + history
    est_seconds = read_chars / READ_SPEED * 60 + LOOKUP_PER_DOC * 3
    return {
        "steps": steps,
        "lookup_actions": len(steps),
        "docs_touched": 3,
        "read_chars": read_chars,
        "est_minutes": round(est_seconds / 60, 1),
        "est_note": f"人工耗时为估算：阅读量/{READ_SPEED}字每分钟 + 每份文档约{LOOKUP_PER_DOC}秒定位",
        "输出": "无结构化排查链、无备件库存信息、无工单/台账沉淀",
    }


def agent_run() -> dict:
    from agent import MaintAgent
    from kg.graph import FaultTree

    # 确定性指标：图谱排查链规模（不依赖 LLM 措辞，可复现）
    kg = FaultTree()
    causes = kg.ranked_causes("F_SERVO_OVERLOAD")

    agent = MaintAgent()
    result = {"rounds": []}
    for label, msg in [
        ("报修", "这台VMC850开机就报伺服过载，X03，主轴转不动，昨天还正常"),
        ("反馈修复", "查了接线，确实是X轴端子松了，打磨紧固后好了，大概用了50分钟"),
    ]:
        agent.trace.clear()
        t0 = time.time()
        reply = agent.chat(msg)
        elapsed = round(time.time() - t0, 1)
        result["rounds"].append({
            "label": label, "seconds": elapsed,
            "tool_calls": len(agent.trace),
            "trace": list(agent.trace),
            "reply_chars": len(reply),
            "reply_head": reply[:120],
            "_reply": reply,
        })
    result["kg_causes"] = len(causes)
    result["kg_check_steps"] = sum(len(c["check_steps"]) for c in causes)
    for r in result["rounds"]:
        r.pop("_reply")
    return result


def main():
    print("== 统计语料规模 ==")
    st = corpus_stats()
    print(json.dumps(st, ensure_ascii=False, indent=2))

    print("\n== 人工基线（基于语料结构的可数事实） ==")
    base = manual_baseline()
    print(json.dumps(base, ensure_ascii=False, indent=2))

    print("\n== Agent 实测（真实调用 DeepSeek 计时） ==")
    ag = agent_run()
    for r in ag["rounds"]:
        print(f"[{r['label']}] {r['seconds']}s｜工具调用 {r['tool_calls']} 次：{' -> '.join(r['trace'])}")
    print(f"图谱排查链：{ag['kg_causes']} 类诱因（由简到繁）· 共 {ag['kg_check_steps']} 条具体检查步骤")

    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
        "corpus": st,
        "manual_baseline": base,
        "agent_measured": ag,
        "note": "人工耗时为阅读速度折算估算（方法已标注）；Agent 耗时为真实 API 计时。其余数字均为可复现统计。",
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已保存：{OUT}")

    m, a = base, ag["rounds"]
    print("\n== 对比摘要 ==")
    print(f"人工：{m['lookup_actions']} 个查找动作 × 跨 {m['docs_touched']} 份文档 × 阅读 {m['read_chars']} 字（约 {m['est_minutes']} 分钟，估算）；无排查链、无备件、无沉淀")
    print(f"Agent：1 句话输入，{a[0]['seconds']}s 返回 {ag['kg_causes']} 类诱因按由简到繁排序、共 {ag['kg_check_steps']} 条具体检查步骤 + 历史案例；修复反馈 {a[1]['seconds']}s 完成入库+回流")


if __name__ == "__main__":
    main()
