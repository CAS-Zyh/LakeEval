import json
import streamlit as st
from ..api_client import api
from .metric_cards import info_box, warning_box, section_title


def render_chat_widget():
    section_title("AI 助手对话")

    # 顶部状态栏：用量 + 知识库
    usage = api.get("/chat/usage")
    kb_status = api.get("/chat/kb_status")
    use_cap = kb_cap = ""
    if usage.get("success"):
        d = usage["data"]
        if d["chat_limit"] == -1:
            use_cap = "AI对话额度：无限（管理员）"
        else:
            use_cap = f"今日对话：{d['chat_used']}/{d['chat_limit']}（剩余 {d['remaining']} 次）"
    if kb_status.get("success"):
        k = kb_status["data"]
        if k["enabled"] and k["chunks"] > 0:
            kb_cap = f"📚 本地知识库：{k['files']} 个文件 / {k['chunks']} 条索引块（阈值 {k['min_score']}）"
        elif k["enabled"]:
            kb_cap = f"📚 本地知识库：{k['kb_dir']} 目录为空，请放入 .txt/.md 文件"
        else:
            kb_cap = "📚 本地知识库：已关闭"
    # 并排展示
    uc1, uc2 = st.columns([2, 3])
    with uc1:
        if use_cap:
            st.caption(use_cap)
    with uc2:
        if kb_cap:
            st.caption(kb_cap)

    if "chat_messages" not in st.session_state:
        history = api.get("/chat/history", {"limit": 20})
        if history.get("success") and history["data"]:
            st.session_state.chat_messages = history["data"]
        else:
            st.session_state.chat_messages = []

    context_label = ""
    if st.session_state.get("ai_context"):
        ctx = st.session_state.ai_context
        context_label = f"已附加评价数据"
        if "total_tli" in ctx:
            context_label += f"（TLI={ctx['total_tli']:.1f}）"
        elif "bqi" in ctx:
            context_label += f"（BQI={ctx['bqi']:.1f}）"
        st.info(context_label)
        if st.button("清除附加数据"):
            st.session_state.pop("ai_context", None)
            st.rerun()

    for msg in st.session_state.chat_messages:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            st.chat_message("user").write(content)
        else:
            st.chat_message("assistant").write(content)

    user_input = st.chat_input("输入消息...")
    if user_input:
        st.chat_message("user").write(user_input)
        st.session_state.chat_messages.append({"role": "user", "content": user_input})

        context_data = st.session_state.get("ai_context")

        with st.chat_message("assistant"):
            # 用 empty 占位符持续重绘累积文本（避免 write_stream 分成多行"长条"）
            text_placeholder = st.empty()
            full_response = ""
            errored = False
            for chunk in api.stream("/chat/message", {
                "message": user_input,
                "context_data": context_data,
            }):
                if "error" in chunk:
                    text_placeholder.error(chunk["error"])
                    errored = True
                    break
                if "content" in chunk:
                    full_response += chunk["content"]
                    # 用 markdown 渲染累积文本，支持表格/列表/公式等
                    text_placeholder.markdown(full_response)
                if chunk.get("done"):
                    break

        if full_response and not errored:
            st.session_state.chat_messages.append({
                "role": "assistant", "content": full_response,
            })

    if st.button("清空对话历史"):
        result = api.delete("/chat/history")
        if result.get("success"):
            st.session_state.chat_messages = []
            st.rerun()
