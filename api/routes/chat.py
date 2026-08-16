import json
from flask import Blueprint, request, jsonify, Response, stream_with_context
from ..auth import require_role, get_client_ip
from ..extensions import db
from ..models import ChatHistory
from ..services.usage import (
    check_and_increment, check_and_increment_guest,
    UsageLimitExceeded, get_today_usage, get_guest_usage,
)
from ..services.deepseek import DeepSeekClient
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    GUEST_MAX_TOKENS, is_deepseek_key_configured,
)

chat_bp = Blueprint("chat", __name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        _client = DeepSeekClient(DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL)
        # 绑定知识库配置
        from config import (
            KB_ENABLED, KB_DIR, KB_CHUNK_SIZE, KB_CHUNK_OVERLAP, KB_TOP_K, KB_MIN_SCORE,
        )
        _client.set_kb_config(
            enabled=KB_ENABLED,
            kb_dir=KB_DIR,
            chunk_size=KB_CHUNK_SIZE,
            overlap=KB_CHUNK_OVERLAP,
            top_k=KB_TOP_K,
            min_score=KB_MIN_SCORE,
        )
    return _client


LAKE_KEYWORDS = {"chla", "tn", "tp", "sd", "cod", "tli", "富营养", "削减", "湖泊", "湖库",
                 "营养", "透明度", "叶绿素", "总磷", "总氮", "bqi", "底栖", "污染"}


def _detect_context_type(message: str, context_data) -> str:
    if context_data:
        return "lake_analysis"
    msg_lower = message.lower()
    for kw in LAKE_KEYWORDS:
        if kw in msg_lower:
            return "hybrid"
    return "general"


@chat_bp.route("/message", methods=["POST"])
@require_role(["admin", "user", "guest"])
def send_message():
    if not is_deepseek_key_configured():
        return jsonify({
            "success": False,
            "error": "DeepSeek API Key 未配置，请在 .env 文件中设置 DEEPSEEK_API_KEY",
            "code": "API_KEY_NOT_CONFIGURED",
        }), 503

    data = request.json or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"success": False, "error": "消息不能为空"}), 400

    user = request.current_user
    is_guest = user.role == "guest"

    # 用量检查
    try:
        if is_guest:
            check_and_increment_guest(user.ip)
        else:
            check_and_increment(user.id)
    except UsageLimitExceeded as e:
        return jsonify({"success": False, "error": str(e), "code": "USAGE_EXCEEDED"}), 429

    # max_tokens 按角色分配
    max_tokens = GUEST_MAX_TOKENS if is_guest else 2048

    context_data = data.get("context_data")
    context_type = _detect_context_type(message, context_data)

    # 历史记录
    if is_guest:
        history_records = ChatHistory.query.filter_by(guest_ip=user.ip) \
            .order_by(ChatHistory.created_at.desc()).limit(10).all()
    else:
        history_records = ChatHistory.query.filter_by(user_id=user.id) \
            .order_by(ChatHistory.created_at.desc()).limit(10).all()
    history_records.reverse()
    history = [{"role": r.role, "content": r.content} for r in history_records]

    # 保存用户消息
    db.session.add(ChatHistory(
        user_id=user.id if not is_guest else None,
        guest_ip=user.ip if is_guest else None,
        role="user", content=message,
        context_type=context_type,
        context_data=json.dumps(context_data) if context_data else None,
    ))
    db.session.commit()

    def generate():
        full_response = []
        try:
            for chunk in _get_client().chat_stream(
                history, message, context_type, context_data, max_tokens=max_tokens
            ):
                full_response.append(chunk)
                yield f"data: {json.dumps({'content': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        assistant_content = "".join(full_response)
        db.session.add(ChatHistory(
            user_id=user.id if not is_guest else None,
            guest_ip=user.ip if is_guest else None,
            role="assistant", content=assistant_content,
            context_type=context_type,
            context_data=json.dumps(context_data) if context_data else None,
        ))
        db.session.commit()
        yield f"data: {json.dumps({'done': True})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@chat_bp.route("/history", methods=["GET"])
@require_role(["admin", "user", "guest"])
def history():
    limit = min(int(request.args.get("limit", 50)), 200)
    user = request.current_user
    if user.role == "guest":
        records = ChatHistory.query.filter_by(guest_ip=user.ip) \
            .order_by(ChatHistory.created_at.desc()).limit(limit).all()
    else:
        records = ChatHistory.query.filter_by(user_id=user.id) \
            .order_by(ChatHistory.created_at.desc()).limit(limit).all()
    records.reverse()
    return jsonify({"success": True, "data": [r.to_dict() for r in records]})


@chat_bp.route("/history", methods=["DELETE"])
@require_role(["admin", "user", "guest"])
def clear_history():
    user = request.current_user
    if user.role == "guest":
        ChatHistory.query.filter_by(guest_ip=user.ip).delete()
    else:
        ChatHistory.query.filter_by(user_id=user.id).delete()
    db.session.commit()
    return jsonify({"success": True})


@chat_bp.route("/usage", methods=["GET"])
@require_role(["admin", "user", "guest"])
def usage():
    user = request.current_user
    if user.role == "guest":
        return jsonify({"success": True, "data": get_guest_usage(user.ip)})
    return jsonify({"success": True, "data": get_today_usage(user.id)})


@chat_bp.route("/kb_status", methods=["GET"])
@require_role(["admin", "user", "guest"])
def kb_status():
    """返回知识库状态：是否启用、文件数、索引块数。用于前端展示。"""
    from config import KB_ENABLED, KB_DIR, KB_TOP_K, KB_MIN_SCORE
    if not KB_ENABLED:
        return jsonify({"success": True, "data": {
            "enabled": False, "files": 0, "chunks": 0,
            "top_k": KB_TOP_K, "min_score": KB_MIN_SCORE,
        }})
    try:
        client = _get_client()
        kb = getattr(client, "_kb", None)
        files = len(kb._mtime_by_file) if kb and kb._mtime_by_file else 0
        chunks = len(kb.chunks) if kb else 0
    except Exception:
        files = 0
        chunks = 0
    return jsonify({"success": True, "data": {
        "enabled": True,
        "kb_dir": KB_DIR,
        "files": files,
        "chunks": chunks,
        "top_k": KB_TOP_K,
        "min_score": KB_MIN_SCORE,
    }})
