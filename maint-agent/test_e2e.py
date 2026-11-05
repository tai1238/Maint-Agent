# -*- coding: utf-8 -*-
"""端到端实测：完整走一遍方案里的演示链路（需 DeepSeek API Key）。

链路：故障报修 -> 图谱推理 + RAG -> 排查指引 -> 修复反馈 -> 入库回流
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agent import MaintAgent

SCENARIO = [
    "这台VMC850开机就报伺服过载，X03，主轴转不动，昨天还正常",
    "查了接线，确实是X轴端子松了，打磨紧固后好了，大概用了50分钟",
]


def main():
    agent = MaintAgent()
    for i, msg in enumerate(SCENARIO, 1):
        print(f"\n{'=' * 60}\n【第{i}轮】师傅：{msg}\n{'-' * 60}")
        reply = agent.chat(msg)
        print(f"Maint-Agent：{reply}")
        if agent.trace:
            print(f"\n[工具调用轨迹] {' -> '.join(agent.trace)}")
    print("\n端到端实测完成。")


if __name__ == "__main__":
    main()
