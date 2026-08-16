from datetime import date
from ..extensions import db
from ..models import User, DailyUsage, GuestUsage
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import GUEST_DAILY_CHAT_LIMIT


class UsageLimitExceeded(Exception):
    pass


# ---------- 注册用户用量 ----------

def check_and_increment(user_id: int) -> None:
    user = User.query.get(user_id)
    if not user:
        raise ValueError("用户不存在")
    if user.daily_chat_limit == -1:
        return

    today = date.today()
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


def get_today_usage(user_id: int) -> dict:
    user = User.query.get(user_id)
    if not user:
        return {"chat_used": 0, "chat_limit": 0, "remaining": 0}

    if user.daily_chat_limit == -1:
        return {"chat_used": 0, "chat_limit": -1, "remaining": -1}

    today = date.today()
    usage = DailyUsage.query.filter_by(user_id=user_id, usage_date=today).first()
    used = usage.chat_count if usage else 0
    return {
        "chat_used": used,
        "chat_limit": user.daily_chat_limit,
        "remaining": max(0, user.daily_chat_limit - used),
    }


# ---------- 游客用量（按 IP） ----------

def check_and_increment_guest(ip: str) -> None:
    today = date.today()
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


def get_guest_usage(ip: str) -> dict:
    today = date.today()
    usage = GuestUsage.query.filter_by(ip_address=ip, usage_date=today).first()
    used = usage.chat_count if usage else 0
    return {
        "chat_used": used,
        "chat_limit": GUEST_DAILY_CHAT_LIMIT,
        "remaining": max(0, GUEST_DAILY_CHAT_LIMIT - used),
    }
