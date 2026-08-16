"""本地知识库 RAG：基于字/词 n-gram TF-IDF + 余弦相似度的轻量检索。
零第三方依赖（仅 numpy，项目已安装）。"""

from __future__ import annotations

import os
import re
import math
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np


@dataclass
class Chunk:
    doc_id: str
    doc_name: str
    index: int
    text: str
    tokens: List[str]  # 预处理后的 token 列表（用于快速检索）


_STOP_CHARS = set("，。、！？；：""''（）【】《》〈〉—…·\t\n\r ,.!?;:()[]<>\"'/-+*=<>|")


def _tokenize(text: str) -> List[str]:
    """中英混合分词：
    - 中文：1-gram 和 2-gram（轻量级中文检索，无需 jieba）
    - 英文/数字：按空白+标点切分后小写，保留 2 位以上单词
    """
    tokens = []
    # 先去掉多余空白
    text = re.sub(r"\s+", " ", text).strip()

    # 拆分中文字符和非中文字符段
    segments = re.findall(r"[\u4e00-\u9fa5]+|[A-Za-z0-9]+(?:[._][A-Za-z0-9]+)*", text)
    for seg in segments:
        if re.fullmatch(r"[\u4e00-\u9fa5]+", seg):
            # 1-gram
            for ch in seg:
                if ch not in _STOP_CHARS:
                    tokens.append(ch)
            # 2-gram
            for i in range(len(seg) - 1):
                bigram = seg[i:i + 2]
                if not (bigram[0] in _STOP_CHARS or bigram[1] in _STOP_CHARS):
                    tokens.append(bigram)
        else:
            w = seg.lower()
            if len(w) >= 2 and w not in {"the", "and", "for", "are", "not", "you", "this",
                                          "that", "with", "from", "have", "has", "was",
                                          "were", "but", "can", "will", "just", "into",
                                          "than", "then", "also", "such", "its"}:
                tokens.append(w)
    return tokens


def _split_into_chunks(doc_id: str, doc_name: str, text: str,
                        chunk_size: int, overlap: int) -> List[Chunk]:
    """按段落优先切分，超长段落再按字符滑动窗口切分。"""
    # 按双换行 / 列表项换行分段落
    paragraphs = re.split(r"\n\s*\n|(?<=[。！？!?；;])\n", text)
    chunks: List[Chunk] = []
    buf = ""
    idx = 0

    def flush(force: bool = False):
        nonlocal buf, idx
        if len(buf.strip()) == 0:
            return
        # 如果 buf 还是超长，按 chunk_size 滑动切片
        if len(buf) > chunk_size:
            start = 0
            while start < len(buf):
                piece = buf[start:start + chunk_size]
                if len(piece.strip()) >= 20:
                    chunks.append(Chunk(
                        doc_id=doc_id, doc_name=doc_name, index=idx,
                        text=piece.strip(), tokens=_tokenize(piece),
                    ))
                    idx += 1
                start += (chunk_size - overlap)
        else:
            chunks.append(Chunk(
                doc_id=doc_id, doc_name=doc_name, index=idx,
                text=buf.strip(), tokens=_tokenize(buf),
            ))
            idx += 1
        buf = ""

    for p in paragraphs:
        p = p.strip()
        if not p:
            flush(force=True)
            continue
        # 尝试合并段落到 buf
        if len(buf) + len(p) + 2 <= chunk_size:
            buf = (buf + "\n" + p).strip() if buf else p
        else:
            flush()
            buf = p
    flush(force=True)
    return chunks


class KnowledgeBase:
    def __init__(self, kb_dir: str, chunk_size: int = 600, overlap: int = 80,
                 top_k: int = 3, min_score: float = 0.12):
        self.kb_dir = kb_dir
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.top_k = top_k
        self.min_score = min_score

        self.chunks: List[Chunk] = []
        self.vocab: dict = {}  # token -> index
        self.idf: np.ndarray | None = None
        self.tfidf_matrix: np.ndarray | None = None
        self._mtime_by_file: dict = {}  # 用于自动 reload
        self._last_reload: float = 0

    # ---------- 加载 / 索引 ----------
    def load(self, project_root: str) -> int:
        """扫描 knowledge_base 目录并建立索引。返回索引块数。

        注意：知识库文件随代码仓库一起提交（只读），所以此处绝不创建或写入本地目录，
        避免在无状态只读云端环境中触发 PermissionError。若目录不存在，直接返回 0。
        """
        import sys, os as _os
        sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
        from config import get_kb_abs_path

        kb_abs = get_kb_abs_path()

        # 绝不创建目录（只读）。目录不存在则视为空知识库
        if not os.path.isdir(kb_abs):
            self.chunks = []
            self.idf = None
            self.tfidf_matrix = None
            return 0

        # 收集所有 .txt / .md
        files = []
        for root, _, names in os.walk(kb_abs):
            for n in names:
                if n.lower().endswith((".txt", ".md")) and not n.startswith("~"):
                    files.append(os.path.join(root, n))

        if not files:
            self.chunks = []
            self.idf = None
            self.tfidf_matrix = None
            return 0

        # 按文件修改时间判断是否需要重索引（简单 mtime 比较）
        try:
            current_mtimes = {f: os.path.getmtime(f) for f in files}
        except OSError:
            current_mtimes = {}
        need_reload = (
            set(current_mtimes) != set(self._mtime_by_file) or
            current_mtimes != self._mtime_by_file
        )
        if not need_reload and self.chunks:
            return len(self.chunks)

        # 读取 & 切块
        all_chunks: List[Chunk] = []
        for f in files:
            try:
                try:
                    with open(f, "r", encoding="utf-8") as fp:
                        text = fp.read()
                except UnicodeDecodeError:
                    with open(f, "r", encoding="gbk", errors="ignore") as fp:
                        text = fp.read()
            except (OSError, PermissionError):
                continue
            doc_id = os.path.relpath(f, kb_abs)
            doc_name = os.path.basename(f)
            all_chunks.extend(_split_into_chunks(doc_id, doc_name, text,
                                                   self.chunk_size, self.overlap))

        if not all_chunks:
            self.chunks = []
            self.idf = None
            self.tfidf_matrix = None
            self._mtime_by_file = current_mtimes
            self._last_reload = time.time()
            return 0

        # 构建词汇表
        vocab: dict = {}
        for c in all_chunks:
            for t in c.tokens:
                if t not in vocab:
                    vocab[t] = len(vocab)
        V = len(vocab)
        N = len(all_chunks)

        # 计算 document frequency（每个 token 出现在多少 chunk 里）
        df = np.zeros(V, dtype=np.float32)
        row_arrs = []
        for c in all_chunks:
            counts = np.zeros(V, dtype=np.float32)
            seen = set()
            for t in c.tokens:
                ti = vocab[t]
                counts[ti] += 1.0
                if ti not in seen:
                    df[ti] += 1.0
                    seen.add(ti)
            # L1 归一化成 TF
            s = counts.sum()
            if s > 0:
                counts /= s
            row_arrs.append(counts)
        tf = np.vstack(row_arrs) if len(row_arrs) > 1 else row_arrs[0].reshape(1, -1)

        # IDF = log((N+1)/(df+1)) + 1 （防止除 0）
        idf = np.log((N + 1.0) / (df + 1.0)) + 1.0

        # TF-IDF 矩阵
        tfidf = tf * idf.reshape(1, -1)

        # L2 归一化行向量，便于点积即余弦相似度
        norms = np.linalg.norm(tfidf, axis=1, keepdims=True)
        norms[norms < 1e-9] = 1.0
        tfidf = tfidf / norms

        self.chunks = all_chunks
        self.vocab = vocab
        self.idf = idf
        self.tfidf_matrix = tfidf
        self._mtime_by_file = current_mtimes
        self._last_reload = time.time()
        return N

    def maybe_reload(self, project_root: str) -> None:
        """每 10s 检查一次文件 mtime，有变化自动重索引。"""
        if time.time() - self._last_reload < 10.0:
            return
        self.load(project_root)

    # ---------- 检索 ----------
    def query(self, question: str, project_root: str) -> List[Tuple[Chunk, float]]:
        """检索最相关的 Top-K 个知识块，返回 [(Chunk, score)]。
        score 是 0~1 之间的余弦相似度，低于 min_score 的会被剔除。
        """
        self.maybe_reload(project_root)
        if not self.chunks or self.tfidf_matrix is None:
            return []

        q_tokens = _tokenize(question)
        if not q_tokens:
            return []

        V = len(self.vocab)
        q_counts = np.zeros(V, dtype=np.float32)
        for t in q_tokens:
            ti = self.vocab.get(t)
            if ti is not None:
                q_counts[ti] += 1.0
        s = q_counts.sum()
        if s == 0:
            return []
        q_tf = q_counts / s
        q_tfidf = q_tf * self.idf
        q_norm = np.linalg.norm(q_tfidf)
        if q_norm < 1e-9:
            return []
        q_tfidf /= q_norm

        # 点积（都已 L2 归一化 → 余弦相似度）
        scores = self.tfidf_matrix @ q_tfidf  # shape (N,)
        scores = scores.astype(np.float64)

        # Top-K 筛选
        k = min(self.top_k, len(self.chunks))
        top_idx = np.argpartition(-scores, k - 1)[:k]
        top_idx = top_idx[np.argsort(-scores[top_idx])]

        out: List[Tuple[Chunk, float]] = []
        for i in top_idx:
            sc = float(scores[i])
            if sc >= self.min_score:
                out.append((self.chunks[i], sc))
        return out


# ---------- 单例 ----------
_kb_instance: Optional[KnowledgeBase] = None


def get_knowledge_base(kb_dir: str, chunk_size: int, overlap: int,
                       top_k: int, min_score: float) -> KnowledgeBase:
    global _kb_instance
    # 如果参数变了则重建（实际项目中参数来自 config，启动后不变）
    if _kb_instance is None or (_kb_instance.kb_dir != kb_dir or
                                 _kb_instance.chunk_size != chunk_size or
                                 _kb_instance.overlap != overlap or
                                 _kb_instance.top_k != top_k or
                                 _kb_instance.min_score != min_score):
        _kb_instance = KnowledgeBase(kb_dir, chunk_size, overlap, top_k, min_score)
    return _kb_instance
