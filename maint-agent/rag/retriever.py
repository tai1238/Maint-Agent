# -*- coding: utf-8 -*-
"""轻量 BM25 检索器：纯 Python 实现，无外部依赖。

用途：检索非结构化文档（报警手册、保养规范、历史维修记录），
作为知识图谱之外细节信息的补充引擎。
中文分词采用字符二元组（bigram），对维修领域短查询足够有效。
"""
from pathlib import Path
from math import log

CORPUS_DIR = Path(__file__).parent / "corpus"
CHUNK_SIZE = 220          # 每块约 220 字
K1, B = 1.5, 0.75         # BM25 经典参数


def _bigrams(text: str) -> list[str]:
    cleaned = "".join(ch for ch in text if not ch.isspace())
    return [cleaned[i : i + 2] for i in range(len(cleaned) - 1)] or ([cleaned] if cleaned else [])


class BM25Retriever:
    def __init__(self, corpus_dir: Path = CORPUS_DIR):
        self.chunks: list[dict] = []   # {"doc": 文件名, "text": 块内容, "tf": 词频, "len": 长度}
        self._build(corpus_dir)

    def _build(self, corpus_dir: Path):
        for path in sorted(corpus_dir.glob("*.txt")):
            text = path.read_text(encoding="utf-8")
            # 按段落聚合后切块，保持语义完整
            for i in range(0, len(text), CHUNK_SIZE):
                chunk = text[i : i + CHUNK_SIZE].strip()
                if len(chunk) < 30:
                    continue
                tokens = _bigrams(chunk)
                tf: dict[str, int] = {}
                for t in tokens:
                    tf[t] = tf.get(t, 0) + 1
                self.chunks.append(
                    {"doc": path.name, "text": chunk, "tf": tf, "len": len(tokens)}
                )
        # 计算 IDF
        n_docs = len(self.chunks)
        df: dict[str, int] = {}
        for c in self.chunks:
            for term in c["tf"]:
                df[term] = df.get(term, 0) + 1
        self.idf = {t: log((n_docs - d + 0.5) / (d + 0.5) + 1) for t, d in df.items()}

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        q_terms = set(_bigrams(query))
        if not q_terms:
            return []
        avg_len = sum(c["len"] for c in self.chunks) / max(len(self.chunks), 1)
        scored = []
        for c in self.chunks:
            score = 0.0
            for term in q_terms:
                if term not in c["tf"]:
                    continue
                score += self.idf.get(term, 0) * c["tf"][term] * (K1 + 1) / (
                    c["tf"][term] + K1 * (1 - B + B * c["len"] / avg_len)
                )
            if score > 0:
                scored.append((score, c))
        scored.sort(key=lambda x: -x[0])
        return [
            {"doc": c["doc"], "text": c["text"], "score": round(s, 3)}
            for s, c in scored[:top_k]
        ]
