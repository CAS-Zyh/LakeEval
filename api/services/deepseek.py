import json
import os
import requests
from typing import Generator, Optional


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DeepSeekClient:
    def __init__(self, api_key: str, model: str = "deepseek-chat",
                 base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._kb_config = None  # (enabled, kb_dir, chunk_size, overlap, top_k, min_score)
        self._kb = None

    def set_kb_config(self, enabled: bool, kb_dir: str, chunk_size: int, overlap: int,
                      top_k: int, min_score: float):
        self._kb_config = (enabled, kb_dir, chunk_size, overlap, top_k, min_score)
        if enabled:
            from .kb import get_knowledge_base
            self._kb = get_knowledge_base(kb_dir, chunk_size, overlap, top_k, min_score)
            self._kb.load(_PROJECT_ROOT)
        else:
            self._kb = None

    def _retrieve_kb(self, question: str) -> list:
        """检索知识库，返回 [{"source":..., "content":..., "score":...}]。"""
        if not self._kb or not self._kb_config:
            return []
        hits = self._kb.query(question, _PROJECT_ROOT)
        if not hits:
            return []
        return [
            {"source": chunk.doc_name, "content": chunk.text, "score": round(sc, 3)}
            for chunk, sc in hits
        ]

    def _build_system_prompt(self, context_type: str, context_data: Optional[dict],
                              kb_hits: list) -> tuple[str, list]:
        base = (
            "你是湖库富营养化评价与决策辅助专家，同时也是通用助手。"
            "你可以回答关于湖库水质评价、TLI（综合营养状态指数）、BQI（底栖状况指数）、"
            "污染物削减方案等专业问题，也可以回答一般性问题。"
            "回答时请用中文，条理清晰，必要时使用markdown格式。"
        )

        kb_context = []
        if kb_hits:
            base += (
                "\n\n【本地知识库参考】\n"
                "以下内容来自用户的本地知识库文件。当你回答用户问题时，"
                "请**优先引用这些本地知识**（若与问题相关）。"
                "引用时可注明文件来源。若本地知识与常识冲突，以本地知识为准；"
                "若本地知识不足，可补充通用专业内容，但请明确区分。\n"
            )
            for i, h in enumerate(kb_hits, 1):
                base += f"\n[{i}] 来源：{h['source']}（相关度 {h['score']}）\n{h['content']}\n"
                kb_context.append(h)

        if context_type in ("lake_analysis", "hybrid") and context_data:
            snapshot_parts = []
            if "total_tli" in context_data:
                snapshot_parts.append(f"综合TLI={context_data['total_tli']:.2f}")
                if "grade_name" in context_data:
                    snapshot_parts.append(f"等级={context_data['grade_name']}")
            if "single_tli" in context_data:
                single = context_data["single_tli"]
                parts = [f"{k}={v:.1f}" for k, v in single.items()]
                snapshot_parts.append(f"单项TLI: {', '.join(parts)}")
            if "contribution_rate" in context_data:
                rates = context_data["contribution_rate"]
                top = sorted(rates.items(), key=lambda x: x[1], reverse=True)[0]
                snapshot_parts.append(f"主要限制因子: {top[0]} (贡献率 {top[1]*100:.1f}%)")
            if "bqi" in context_data:
                snapshot_parts.append(f"BQI={context_data['bqi']:.2f}")
                if "grade_name" in context_data:
                    snapshot_parts.append(f"底栖等级={context_data['grade_name']}")
            if "ratio" in context_data:
                snapshot_parts.append(f"建议统一削减率={context_data['ratio']*100:.1f}%")
            if "tli" in context_data and "ratio" in context_data:
                snapshot_parts.append(f"削减后预计TLI={context_data['tli']:.2f}")

            if snapshot_parts:
                base += "\n\n【当前湖泊评价快照】\n" + "\n".join(f"- {p}" for p in snapshot_parts)
                base += "\n请基于上述数据回答用户问题，引用具体数值。"

        return base, kb_context

    def chat_stream(
        self,
        history: list,
        message: str,
        context_type: str = "general",
        context_data: Optional[dict] = None,
        max_tokens: int = 2048,
    ) -> Generator[str, None, None]:
        # 先检索知识库（若用户消息太短则跳过，避免检索无意义噪声）
        kb_hits = self._retrieve_kb(message) if len(message.strip()) >= 2 else []
        system_prompt, _ = self._build_system_prompt(context_type, context_data, kb_hits)

        messages = [{"role": "system", "content": system_prompt}]
        for h in history[-10:]:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "max_tokens": max_tokens,
        }

        response = requests.post(url, json=payload, headers=headers, stream=True, timeout=60)
        response.raise_for_status()

        for line in response.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8")
            if not line_str.startswith("data: "):
                continue
            data_str = line_str[6:]
            if data_str.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content
            except (json.JSONDecodeError, IndexError, KeyError):
                continue
