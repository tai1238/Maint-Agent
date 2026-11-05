# -*- coding: utf-8 -*-
"""Maint-Agent Web 演示服务。

启动：python webapp.py  （浏览器打开 http://127.0.0.1:7860）
说明：单用户演示模式，会话状态保存在服务端进程内。
"""
import json
import sys
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, str(Path(__file__).parent))

from agent import MaintAgent  # noqa: E402
from kg_review import _read_queue, approve  # noqa: E402
from tools import DATA_DIR, WORKORDER_DIR  # noqa: E402

app = Flask(__name__, static_folder="static")
STATE_DIR = Path(__file__).parent / "data"
_agent: MaintAgent | None = None


def get_agent() -> MaintAgent:
    global _agent
    if _agent is None:
        _agent = MaintAgent()
    return _agent


# ---------- 页面 ----------

@app.get("/")
def index():
    return send_from_directory("static", "index.html")


# ---------- 对话 ----------

@app.post("/api/chat")
def chat():
    data = request.get_json(force=True)
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "空消息"}), 400
    agent = get_agent()
    agent.trace.clear()
    try:
        reply = agent.chat(message)
    except Exception as e:  # noqa: BLE001 - 演示环境下把异常转成可读回复
        return jsonify({"error": f"调用失败：{e}"}), 500
    return jsonify({"reply": reply, "trace": agent.trace})


@app.post("/api/reset")
def reset():
    """清空会话历史，恢复初始状态（演示重跑用）。"""
    global _agent
    _agent = None
    return jsonify({"ok": True})


# ---------- 数据面板 ----------

@app.get("/api/kg")
def kg():
    """故障树全量数据，前端渲染图谱面板。"""
    return jsonify(get_agent().kg.data)


@app.get("/api/workorders")
def workorders():
    orders = []
    for path in sorted(WORKORDER_DIR.glob("WO-*.json"), reverse=True):
        orders.append(json.loads(path.read_text(encoding="utf-8")))
    return jsonify(orders)


@app.get("/api/parts")
def parts():
    inventory = json.loads((DATA_DIR / "parts_inventory.json").read_text(encoding="utf-8"))
    return jsonify(inventory["parts"])


@app.get("/api/repairs")
def repairs():
    log = json.loads((DATA_DIR / "repair_log.json").read_text(encoding="utf-8"))
    return jsonify(list(reversed(log["records"])))


@app.get("/api/pending")
def pending():
    """知识回流待审核队列（含已审核），前端展示闭环状态。"""
    return jsonify(list(reversed(_read_queue())))


@app.post("/api/review/approve")
def review_approve():
    """知识回流一键审核：案例根因并入故障树图谱。"""
    data = request.get_json(force=True)
    rid = (data.get("record_id") or "").strip()
    if not rid:
        return jsonify({"error": "缺少 record_id"}), 400
    try:
        return jsonify({"message": approve(rid)})
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": f"审核并入失败：{e}"}), 500


if __name__ == "__main__":
    # threaded=False：演示模式单会话，避免多线程共享 Agent 状态
    app.run(host="127.0.0.1", port=7860, threaded=False)
