"""数据库安全操作工具：统一处理无状态环境下的 DB 写入失败。

在 Render Free 等无持久化磁盘、文件系统只读、或内存数据库（sqlite:///:memory:）
环境中，db.session.commit() 虽然对内存 DB 可用，但遇到并发/重启等极端情况仍需
优雅降级，避免 500。

核心用法：
    from ..safe_db import safe_commit
    db.session.add(obj)
    ok, err = safe_commit()
    if not ok:
        return jsonify({"success":False, "error": err, "code":"DB_WRITE_FAILED"}), 503
"""
from __future__ import annotations

from typing import Tuple
from sqlalchemy.exc import SQLAlchemyError, OperationalError

from .extensions import db
from config import DB_EPHEMERAL


EPHEMERAL_ERR_HINT = (
    "当前服务运行在无持久化环境，注册/历史记录等写入功能受限。"
    "（可在挂载持久化磁盘后恢复完整功能。）"
)


def safe_commit() -> Tuple[bool, str]:
    """安全提交：捕获所有数据库异常并回滚。返回 (成功? , 错误信息)。"""
    try:
        db.session.commit()
        return True, ""
    except (SQLAlchemyError, OperationalError, OSError, PermissionError) as e:
        db.session.rollback()
        msg = str(e)
        if DB_EPHEMERAL:
            return False, f"数据保存失败（临时模式）。{EPHEMERAL_ERR_HINT} 详情：{msg[:120]}"
        return False, f"数据库写入失败：{msg[:200]}"


def safe_delete(obj) -> Tuple[bool, str]:
    db.session.delete(obj)
    return safe_commit()


def safe_add(obj, *, commit: bool = True) -> Tuple[bool, str]:
    db.session.add(obj)
    if not commit:
        return True, ""
    return safe_commit()


def is_ephemeral_mode() -> bool:
    """当前是否处于临时内存数据库模式（数据不持久化）。"""
    return DB_EPHEMERAL
