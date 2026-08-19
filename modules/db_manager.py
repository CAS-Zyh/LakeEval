"""底栖动物耐污值数据库管理模块。

职责：
- 从 JSON 种子文件自动导入 standard_tolerance 表
- 提供 get_tolerance_dataframe() 供 BenthicBQICalculator 初始化
- 物种名智能匹配（属级精确 → 科级精确 → 模糊 LIKE）
- 分页搜索

依赖：SQLAlchemy（通过 api.extensions.db），可独立于 Flask 请求上下文运行。
"""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# ── 内存缓存 ──────────────────────────────────────────────
_tolerance_cache: Dict[str, float] = {}
_cache_lock = threading.Lock()
_cache_loaded = False

# ── 旧版兜底字典 ──────────────────────────────────────────
FALLBACK_TOLERANCE: Dict[str, float] = {
    "颤蚓属": 0, "水丝蚓属": 0, "带丝蚓属": 0, "盲蚓属": 0,
    "仙女虫属": 1, "尾盘虫属": 1, "管水蚓属": 1, "摇蚊幼虫": 1, "红虫": 1,
    "多足摇蚊": 2, "小摇蚊": 2, "长足摇蚊": 2, "双翅目幼虫": 2,
    "石蛾幼虫": 3, "蜉蝣幼虫": 3, "蜻蜒幼虫": 3, "豆娘幼虫": 3,
    "毛翅目幼虫": 3, "软体动物": 3, "螺类": 3, "蜻蜓若虫": 3, "蜉蝣若虫": 3,
    "蚌类": 4, "河蚬": 4, "襀翅目若虫": 4, "石蝇幼虫": 4,
    "钩虾": 4, "端足类": 4, "十足类": 4,
    "清洁种": 5,
}

DEFAULT_TOLERANCE = 5.0


# ═══════════════════════════════════════════════════════════════
# 种子数据导入
# ═══════════════════════════════════════════════════════════════

def seed_from_json(project_root: str) -> bool:
    """若 standard_tolerance 表为空，从 data/tolerance_seed.json 自动导入。

    返回 True 表示执行了导入，False 表示已有数据或文件不存在。
    """
    try:
        from api.models import StandardTolerance
        from api.extensions import db
    except ImportError:
        logger.warning("无法导入 api.models / api.extensions，跳过种子导入")
        return False

    if StandardTolerance.query.count() > 0:
        return False

    json_path = os.path.join(project_root, "data", "tolerance_seed.json")
    if not os.path.exists(json_path):
        json_path = os.path.join(project_root, "data", "benthic_tolerance.json")
        if not os.path.exists(json_path):
            logger.warning("种子文件不存在: data/tolerance_seed.json")
            return False

    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    records = payload.get("records", [])
    if not records:
        return False

    objs = []
    for r in records:
        objs.append(StandardTolerance(
            phylum=r.get("phylum", "") or "",
            class_name=r.get("class_name", "") or "",
            order_name=r.get("order_name", "") or "",
            family=r.get("family", "") or "",
            genus=r.get("genus", "") or "",
            tolerance_value=float(r.get("tolerance_value", DEFAULT_TOLERANCE)),
        ))

    db.session.bulk_save_objects(objs)
    db.session.commit()
    logger.info("种子导入完成：%d 条 → standard_tolerance（来源：%s）", len(objs), payload.get("source", ""))
    return True


# ═══════════════════════════════════════════════════════════════
# DataFrame 接口（供 BenthicBQICalculator 初始化）
# ═══════════════════════════════════════════════════════════════

def get_tolerance_dataframe() -> pd.DataFrame:
    """返回 standard_tolerance 表的完整 DataFrame。
    列：id, phylum, class_name, order_name, family, genus, tolerance_value。
    供 BenthicBQICalculator 初始化时调用。
    """
    try:
        from api.models import StandardTolerance
        from api.extensions import db

        rows = StandardTolerance.query.all()
        if not rows:
            # 表为空，尝试从 JSON 直接加载
            return _load_dataframe_from_json()

        return pd.DataFrame([r.to_dict() for r in rows])
    except Exception:
        return _load_dataframe_from_json()


def _load_dataframe_from_json() -> pd.DataFrame:
    """从 JSON 种子文件直接加载 DataFrame（无 DB 时兜底）。"""
    import sys
    for candidate in [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tolerance_seed.json"),
        os.path.join(os.getcwd(), "data", "tolerance_seed.json"),
    ]:
        if os.path.exists(candidate):
            with open(candidate, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return pd.DataFrame(payload["records"])
    return pd.DataFrame(columns=["phylum", "class_name", "order_name", "family", "genus", "tolerance_value"])


# ═══════════════════════════════════════════════════════════════
# 耐受值字典缓存（兼容旧接口）
# ═══════════════════════════════════════════════════════════════

def load_tolerance_dict() -> Dict[str, float]:
    """从 standard_tolerance 表加载耐污值字典到内存缓存。

    优先级：属名 → 科名 → 旧版兜底字典。
    """
    global _cache_loaded
    with _cache_lock:
        if _cache_loaded:
            return _tolerance_cache

        try:
            from api.models import StandardTolerance
            from api.extensions import db
            from flask import current_app

            if not current_app:
                return FALLBACK_TOLERANCE

            records = db.session.query(
                StandardTolerance.genus,
                StandardTolerance.family,
                StandardTolerance.tolerance_value,
            ).all()

            mapping: Dict[str, float] = {}
            for genus, family, tv in records:
                tv = float(tv)
                for name in (genus, family):
                    n = (name or "").strip()
                    if n and n not in mapping:
                        mapping[n] = tv
            _tolerance_cache.update(mapping)
            _cache_loaded = True
            return _tolerance_cache
        except Exception:
            return FALLBACK_TOLERANCE


def reload_cache() -> int:
    global _cache_loaded
    with _cache_lock:
        _tolerance_cache.clear()
        _cache_loaded = False
    return len(load_tolerance_dict())


def get_tolerance(name: str) -> Optional[float]:
    if not name:
        return None
    name = name.strip()
    db_dict = load_tolerance_dict()
    if name in db_dict:
        return db_dict[name]
    if name in FALLBACK_TOLERANCE:
        return FALLBACK_TOLERANCE[name]
    return None


# ═══════════════════════════════════════════════════════════════
# 物种名智能匹配
# ═══════════════════════════════════════════════════════════════

def match_species(name: str) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """智能匹配物种名到耐污值。

    匹配优先级：属 → 科 → 目 → 纲 → 门 逐级向上精确匹配，再模糊 LIKE。
    返回 (tolerance_value, matched_name, match_level)。
    match_level: "genus" | "family" | "order" | "class" | "phylum" | "fuzzy" | None
    """
    if not name:
        return None, None, None
    n = name.strip()

    try:
        from api.models import StandardTolerance
        from api.extensions import db
        from sqlalchemy import or_
    except ImportError:
        tv = FALLBACK_TOLERANCE.get(n, DEFAULT_TOLERANCE)
        return tv, n, "default"

    # 精确匹配：属 → 科 → 目 → 纲 → 门，逐级向上
    for field, level in (
        (StandardTolerance.genus, "genus"),
        (StandardTolerance.family, "family"),
        (StandardTolerance.order_name, "order"),
        (StandardTolerance.class_name, "class"),
        (StandardTolerance.phylum, "phylum"),
    ):
        row = db.session.query(StandardTolerance.tolerance_value).filter(field == n).first()
        if row:
            return float(row.tolerance_value), n, level

    # 模糊匹配
    row = db.session.query(StandardTolerance.tolerance_value).filter(
        or_(
            StandardTolerance.genus.like(f"%{n}%"),
            StandardTolerance.family.like(f"%{n}%"),
            StandardTolerance.order_name.like(f"%{n}%"),
            StandardTolerance.class_name.like(f"%{n}%"),
            StandardTolerance.phylum.like(f"%{n}%"),
        )
    ).first()
    if row:
        return float(row.tolerance_value), n, "fuzzy"

    return None, None, None


# ═══════════════════════════════════════════════════════════════
# 数据库搜索
# ═══════════════════════════════════════════════════════════════

def search_species(
    query: str = "",
    page: int = 1,
    page_size: int = 50,
) -> Tuple[List[dict], dict]:
    """搜索耐污值数据库。返回 (records, meta)。"""
    try:
        from api.models import StandardTolerance
        from api.extensions import db
        from sqlalchemy import or_
    except ImportError:
        return [], {"total": 0, "page": 1, "page_size": page_size, "pages": 0, "query": query}

    q = (query or "").strip()
    qs = StandardTolerance.query
    if q:
        like = f"%{q}%"
        qs = qs.filter(or_(
            StandardTolerance.phylum.like(like),
            StandardTolerance.class_name.like(like),
            StandardTolerance.order_name.like(like),
            StandardTolerance.family.like(like),
            StandardTolerance.genus.like(like),
        ))

    total = qs.count()
    rows = qs.order_by(StandardTolerance.id).offset((page - 1) * page_size).limit(page_size).all()
    return (
        [r.to_dict() for r in rows],
        {
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, (total + page_size - 1) // page_size),
            "query": q,
        },
    )