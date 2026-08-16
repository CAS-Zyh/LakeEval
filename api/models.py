from datetime import date, datetime
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    daily_chat_limit = db.Column(db.Integer, nullable=False, default=10)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "daily_chat_limit": self.daily_chat_limit,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }


class DailyUsage(db.Model):
    __tablename__ = "daily_usage"
    __table_args__ = (db.UniqueConstraint("user_id", "usage_date"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    usage_date = db.Column(db.Date, nullable=False, default=date.today)
    chat_count = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "usage_date": self.usage_date.isoformat(),
            "chat_count": self.chat_count,
        }


class CalculationRecord(db.Model):
    __tablename__ = "calculation_records"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    type = db.Column(db.String(20), nullable=False)
    input_data = db.Column(db.Text, nullable=False)
    result = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "input_data": self.input_data,
            "result": self.result,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ChatHistory(db.Model):
    __tablename__ = "chat_history"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    guest_ip = db.Column(db.String(45), nullable=True, index=True)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    context_type = db.Column(db.String(20), default="general")
    context_data = db.Column(db.Text, nullable=True)
    tokens_used = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "context_type": self.context_type,
            "context_data": self.context_data,
            "tokens_used": self.tokens_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class GuestUsage(db.Model):
    __tablename__ = "guest_usage"
    __table_args__ = (db.UniqueConstraint("ip_address", "usage_date"),)
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    usage_date = db.Column(db.Date, nullable=False, default=date.today)
    chat_count = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self):
        return {
            "ip_address": self.ip_address,
            "usage_date": self.usage_date.isoformat(),
            "chat_count": self.chat_count,
        }
