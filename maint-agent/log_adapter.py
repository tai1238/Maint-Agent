# -*- coding: utf-8 -*-
"""CNC 日志采集适配层（演示版）。

真实采集卡需要按机床厂家协议对接硬件，本层先把"日志流接入"的软件链路完整跑通：
  仿真日志流 -> 监控器滚动解析 -> 报警码匹配故障树 -> 自动推送排查链路 + 生成工单。
区域赛阶段接入真实采集卡时，仅需替换 stream 来源，monitor 与业务逻辑零改动。

用法：
    python log_adapter.py demo     # 单终端演示：后台模拟日志流 + 前台监控告警
    python log_adapter.py stream   # 仅模拟日志流
    python log_adapter.py monitor  # 仅监控已有日志文件
"""
import random
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from kg.graph import FaultTree  # noqa: E402
from tools import dispatch  # noqa: E402

LOG_DIR = Path(__file__).parent / "data" / "cnc_log"
LOG_FILE = LOG_DIR / "vmc850_stream.log"

# 仿真日志模板（演示数据）：正常心跳 + 偶发报警
HEARTBEATS = [
    "{ts} VMC850 | X{pos:.3f} Y{pos2:.3f} | 主轴 {rpm} rpm | 状态:运行",
    "{ts} VMC850 | 润滑压力 {p:.1f} MPa | 冷却液 {c:.0f}% | 状态:运行",
    "{ts} VMC850 | 程序 O1024 段 N{seg} | 进给 {f} mm/min | 状态:运行",
]
ALARMS = [
    "!!! ALARM 431 伺服过载 X轴 状态:急停",
    "!!! ALARM 506 润滑压力异常 状态:警告",
    "!!! ALARM 751 主轴过热 状态:警告",
]


def _fmt(ts):
    return ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def stream_loop(interval: float = 2.0, alarm_after: int = 4, stop: threading.Event | None = None):
    """模拟采集卡：周期写运行心跳，第 alarm_after 个周期注入一条随机报警。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stop = stop or threading.Event()
    count = 0
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        while not stop.is_set():
            ts = datetime.now()
            if count > 0 and count % alarm_after == 0:
                line = _fmt(ts) + " " + random.choice(ALARMS)
            else:
                line = random.choice(HEARTBEATS).format(
                    ts=_fmt(ts), pos=random.uniform(50, 450), pos2=random.uniform(0, 300),
                    rpm=random.choice([3000, 4500, 6000]), p=random.uniform(1.8, 2.4),
                    c=random.uniform(60, 90), seg=random.randint(100, 900),
                    f=random.choice([800, 1200, 1600]))
            f.write(line + "\n")
            f.flush()
            count += 1
            stop.wait(interval)


def parse_and_alert(line: str, kg: FaultTree) -> str | None:
    """从一行日志解析报警并给出处置建议；正常日志返回 None。"""
    if "ALARM" not in line:
        return None
    fault = kg.match_fault(line)
    if not fault:
        return f"  [监控器] 检测到未登记报警，已转发 RAG 检索并标记待补充图谱：{line.strip()}"
    causes = kg.ranked_causes(fault["id"])
    top = causes[0] if causes else None
    out = [
        f"  [监控器] 报警命中图谱：{fault['name']}（{fault['device']}，严重度 {fault['severity']}）",
        f"  [监控器] 建议第一步（由简到繁第 1 项）：{top['name']} —— {top['check_steps'][0]}",
    ]
    if top.get("parts"):
        p = kg.get_part(top["parts"][0])
        out.append(f"  [监控器] 可能需要备件：{p['name']}（{p['model']}）-> " +
                   dispatch("query_parts", {"keyword": p["name"]}).splitlines()[1].strip())
    out.append("  [监控器] " + dispatch("create_workorder", {
        "device": fault["device"], "fault_desc": fault["phenomenon"],
        "suspected_cause": top["name"], "priority": "高" if fault["severity"] == "高" else "中",
    }))
    return "\n".join(out)


def monitor_loop(stop: threading.Event | None = None):
    """滚动监控日志文件（等价真实采集卡的推送回调），新报警触发告警与建单。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.touch(exist_ok=True)
    kg = FaultTree()
    pos = 0
    print(f"[监控器] 开始监控 {LOG_FILE.name}（Ctrl+C 退出）")
    while not (stop and stop.is_set()):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            f.seek(pos)
            for line in f:
                alert = parse_and_alert(line, kg)
                if alert:
                    print(alert)
            pos = f.tell()
        time.sleep(1)


def demo(duration: float = 20.0):
    """单终端演示：线程模拟日志流，主线程监控告警，约 20 秒自动结束。"""
    stop = threading.Event()
    t = threading.Thread(target=stream_loop, kwargs={"stop": stop}, daemon=True)
    print(f"== Maint-Agent 采集日志适配层演示（仿真数据流，真实采集卡区域赛接入） ==")
    t.start()
    threading.Timer(duration, stop.set).start()
    try:
        monitor_loop(stop)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if cmd == "demo":
        demo()
    elif cmd == "stream":
        stream_loop()
    elif cmd == "monitor":
        try:
            monitor_loop()
        except KeyboardInterrupt:
            print("\n[监控器] 已退出")
    else:
        print(__doc__)
