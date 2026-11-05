# -*- coding: utf-8 -*-
"""故障树知识图谱：加载与查询推理。

实体：故障(F) - 诱因(C) - 备件(P)，通过 fault -> causes -> parts 链路组织。
核心能力：按报警码/现象匹配故障，按"由简到繁"排序诱因（先低成本低风险，
          再按先验概率），沿链路取备件信息。
"""
import json
from pathlib import Path

KG_PATH = Path(__file__).parent / "fault_tree.json"

# 排序权重：成本越低越先查，同成本下先验概率高者优先
_COST_ORDER = {"低": 0, "中": 1, "高": 2}


class FaultTree:
    def __init__(self, path: Path = KG_PATH):
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.faults = self.data["faults"]
        self.causes = self.data["causes"]
        self.parts = self.data["parts"]

    # ---------- 故障匹配 ----------

    def match_fault(self, text: str) -> dict | None:
        """根据报警码或故障关键词匹配故障节点。

        优先匹配报警码（强证据），其次按名称/现象关键词包含匹配。
        """
        # 1) 报警码匹配：提取文本中的数字或 X03 形式代码
        for fid, fault in self.faults.items():
            for code in fault["alarm_codes"]:
                if code in text:
                    return {"id": fid, **fault}

        # 2) 名称/现象关键词匹配（粗词完整命中 + 字符二元组滑窗命中，合计
        #    达到阈值才判匹配，既容忍口语化描述又避免误报）
        best, best_hits = None, 0
        for fid, fault in self.faults.items():
            kws = (fault["name"], fault["phenomenon"])
            full = sum(1 for kw in kws for w in _split_keywords(kw) if w and w in text)
            grams = sum(1 for kw in kws for bg in _bigrams(kw) if bg in text)
            hits = full + grams
            if hits > best_hits:
                best, best_hits = {"id": fid, **fault}, hits
        return best if best_hits >= 3 else None

    def get_fault(self, fault_id: str) -> dict | None:
        fault = self.faults.get(fault_id)
        return {"id": fault_id, **fault} if fault else None

    # ---------- 推理 ----------

    def ranked_causes(self, fault_id: str) -> list[dict]:
        """返回按"由简到繁"排序的诱因清单：成本升序 -> 先验概率降序。"""
        fault = self.faults.get(fault_id)
        if not fault:
            return []
        items = []
        for cid in fault["causes"]:
            cause = self.causes[cid]
            items.append(
                {
                    "id": cid,
                    "name": cause["name"],
                    "prob": cause["prob"],
                    "cost": cause["cost"],
                    "risk": cause["risk"],
                    "check_steps": cause["check_steps"],
                    "risk_note": cause.get("risk_note", ""),
                    "parts": cause["parts"],
                }
            )
        items.sort(key=lambda c: (_COST_ORDER.get(c["cost"], 9), -c["prob"]))
        return items

    def get_part(self, part_id: str) -> dict | None:
        part = self.parts.get(part_id)
        return {"id": part_id, **part} if part else None

    # ---------- 知识回流：维修案例并入图谱 ----------

    def find_cause_by_name(self, fault_id: str, name: str) -> str | None:
        """在指定故障下按名称查诱因，用于审核合并时去重。"""
        for cid in self.faults[fault_id]["causes"]:
            if self.causes[cid]["name"] == name:
                return cid
        return None

    def add_cause(self, fault_id: str, name: str, check_steps: list[str],
                  cost: str = "中", risk: str = "中", prob: float = 0.10,
                  parts: list[str] | None = None, source: str = "") -> str:
        """把审核通过的维修案例沉淀为新诱因节点（内存操作，需显式 save）。

        同名诱因已存在时不重复创建，直接返回已有诱因 ID。
        """
        if fault_id not in self.faults:
            raise KeyError(f"图谱中不存在故障 {fault_id}")
        existing = self.find_cause_by_name(fault_id, name)
        if existing:
            return existing
        cid = f"C_REFLOW_{len([c for c in self.causes if c.startswith('C_REFLOW')]) + 1:03d}"
        cause = {
            "name": name,
            "prob": prob,
            "cost": cost,
            "risk": risk,
            "check_steps": check_steps,
            "parts": parts or [],
        }
        if source:
            cause["risk_note"] = f"来源：现场维修回流案例（{source}），经人工审核并入"
        self.causes[cid] = cause
        self.faults[fault_id]["causes"].append(cid)
        return cid

    def save(self, path: Path | None = None):
        """写回图谱文件，版本号自动 +0.1。"""
        path = path or KG_PATH
        ver = self.data["meta"].get("version", "1.0")
        major, minor = ver.split(".")
        self.data["meta"]["version"] = f"{major}.{int(minor) + 1}"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def list_faults(self) -> list[dict]:
        return [
            {"id": fid, "name": f["name"], "alarm_codes": f["alarm_codes"]}
            for fid, f in self.faults.items()
        ]


def _split_keywords(text: str) -> list[str]:
    """把故障名称/现象切成粗粒度关键词，用于包含匹配。"""
    separators = ("、", "/", "，", ",", "或", "与", " ")
    for sep in separators:
        text = text.replace(sep, "|")
    return [w for w in text.split("|") if len(w) >= 2]


def _bigrams(text: str) -> list[str]:
    """中文名称/现象的字符二元组，容忍口语化描述中的插入语。"""
    cleaned = [c for c in text if c not in "、/，,。或与 "]
    return ["".join(cleaned[i:i + 2]) for i in range(len(cleaned) - 1)]
