from datetime import date
from collections import defaultdict
from ..extensions import db
from ..models import User, DailyUsage, GuestUsage
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import GUEST_DAILY_CHAT_LIMIT, DB_EPHEMERAL


class UsageLimitExceeded(Exception):
    pass


# ---------- 进程内内存计数兜底（无状态/只读DB环境用） ----------
# 结构: _mem_user[(user_id, date)] = count
_mem_user: dict = defaultdict(lambda: defaultdict(int))
# 结构: _mem_guest[(ip, date)] = count
_mem_guest: dict = defaultdict(lambda: defaultdict(int))


# ---------- 注册用户用量 ----------

def check_and_increment(user_id: int) -> None:
    user = _safe_get_user(user_id)
    if not user:
        raise ValueError("用户不存在")
    if user.daily_chat_limit == -1:
        return

    today = date.today()

    # 尝试数据库计数
    try:
        usage = DailyUsage.query.filter_by(user_id=user_id, usage_date=today).first()
        if not usage:
            usage = DailyUsage(user_id=user_id, usage_date=today, chat_count=0)
            db.session.add(usage)

        if usage.chat_count >= user.daily_chat_limit:
            raise UsageLimitExceeded(
                f"今日对话次数已达上限（{user.daily_chat_limit}次），请明天再试"
            )
        usage.chat_count += 1
        db.session.commit()
        return
    except UsageLimitExceeded:
        raise
    except Exception:
        pass  # 数据库失败 -> 降级内存计数

    # 降级：进程内内存计数
    if _mem_user[user_id][today] >= user.daily_chat_limit:
        raise UsageLimitExceeded(
            f"今日对话次数已达上限（{user.daily_chat_limit}次），请明天再试"
        )
    _mem_user[user_id][today] += 1


def get_today_usage(user_id: int) -> dict:
    user = _safe_get_user(user_id)
    if not user:
        return {"chat_used": 0, "chat_limit": 0, "remaining": 0}

    if user.daily_chat_limit == -1:
        return {"chat_used": 0, "chat_limit": -1, "remaining": -1}

    today = date.today()
    try:
        usage = DailyUsage.query.filter_by(user_id=user_id, usage_date=today).first()
        used = usage.chat_count if usage else 0
    except Exception:
        used = _mem_user[user_id][today]
    return {
        "chat_used": used,
        "chat_limit": user.daily_chat_limit,
        "remaining": max(0, user.daily_chat_limit - used),
    }


# ---------- 游客用量（按 IP） ----------

def check_and_increment_guest(ip: str) -> None:
    today = date.today()
    try:
        usage = GuestUsage.query.filter_by(ip_address=ip, usage_date=today).first()
        if not usage:
            usage = GuestUsage(ip_address=ip, usage_date=today, chat_count=0)
            db.session.add(usage)

        if usage.chat_count >= GUEST_DAILY_CHAT_LIMIT:
            raise UsageLimitExceeded(
                f"游客每日对话上限为 {GUEST_DAILY_CHAT_LIMIT} 次，请明天再试或注册账号获取更多额度"
            )
        usage.chat_count += 1
        db.session.commit()
        return
    except UsageLimitExceeded:
        raise
    except Exception:
        pass  # 数据库失败 -> 降级内存计数

    if _mem_guest[ip][today] >= GUEST_DAILY_CHAT_LIMIT:
        raise UsageLimitExceeded(
            f"游客每日对话上限为 {GUEST_DAILY_CHAT_LIMIT} 次，请明天再试或注册账号获取更多额度"
        )
    _mem_guest[ip][today] += 1


def get_guest_usage(ip: str) -> dict:
    today = date.today()
    try:
        usage = GuestUsage.query.filter_by(ip_address=ip, usage_date=today).first()
        used = usage.chat_count if usage else 0
    except Exception:
        used = _mem_guest[ip][today]
    return {
        "chat_used": used,
        "chat_limit": GUEST_DAILY_CHAT_LIMIT,
        "remaining": max(0, GUEST_DAILY_CHAT_LIMIT - used),
    }


def _safe_get_user(user_id: int):
    """在 ephemeral 模式/DB 异常时，避免因为查询失败导致登录用户功能全挂：
    返回一个内存中的"假用户对象"，具有读取 daily_chat_limit 等功能。"""
    try:
        u = User.query.get(user_id)
        if u:
            return u
    except Exception:
        pass
    # 兜底：创建一个轻量对象，只提供 daily_chat_limit 属性
    import config as _cfg
    class _FallbackUser:
        id = user_id
        daily_chat_limit = _cfg.USER_DAILY_CHAT_LIMIT
        role = "user"
    return _FallbackUser()

