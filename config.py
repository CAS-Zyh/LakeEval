import os
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录绝对路径（基于当前文件位置，保证任何入口调用都一致）
# 不要基于 getcwd()，否则 Render/Streamlit 的工作目录变化会失效
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

JWT_SECRET = os.getenv("JWT_SECRET", "lakeeval-dev-secret")
JWT_EXPIRY_HOURS = 24

FLASK_PORT = int(os.getenv("FLASK_PORT", "5001"))
STREAMLIT_PORT = int(os.getenv("STREAMLIT_PORT", "8501"))
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")

# --- 数据库 ---
# 无状态云端环境（无持久化磁盘）默认：sqlite:///:memory:（纯内存，重启即清空）
# 本地/有磁盘环境通过 .env 设置为 sqlite:///lake_eval.db
# 也可以在渲染免费层挂持久磁盘到 instance/，设置 DATABASE_URI=sqlite:///instance/lake_eval.db
DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///:memory:")

# 判断是否为"临时内存数据库"（用于在 UI/API 中给用户提示：数据不会持久化）
DB_EPHEMERAL = DATABASE_URI.strip().lower() in ("sqlite:///:memory:", "sqlite:///file::memory:?cache=shared")

DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")

# --- 游客限制 ---
GUEST_DAILY_CHAT_LIMIT = int(os.getenv("GUEST_DAILY_CHAT_LIMIT", "5"))
GUEST_MAX_TOKENS = int(os.getenv("GUEST_MAX_TOKENS", "500"))
GUEST_TOKEN_EXPIRY_HOURS = int(os.getenv("GUEST_TOKEN_EXPIRY_HOURS", "2"))

USER_DAILY_CHAT_LIMIT = int(os.getenv("USER_DAILY_CHAT_LIMIT", "10"))

# --- 安全 ---
# CORS 白名单（逗号分隔）。公网部署时改为你的前端域名。
# 默认包含：
#   - 本地开发 (localhost / 127.0.0.1)
#   - 单体部署子进程同源请求（Streamlit UI -> 本机 Flask）
#   - Streamlit Cloud 所有免费域名 (*.streamlit.app)，便于直接使用
_ST_DEFAULT_ORIGINS = [
    f"http://localhost:{STREAMLIT_PORT}",
    f"http://127.0.0.1:{STREAMLIT_PORT}",
    "https://*.streamlit.app",
    f"http://localhost:{FLASK_PORT}",
    f"http://127.0.0.1:{FLASK_PORT}",
]
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "ALLOWED_ORIGINS",
        ",".join(_ST_DEFAULT_ORIGINS)
    ).split(",") if o.strip()
]
# 全局 IP 速率限制（每分钟请求数）
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

# --- 本地知识库 RAG ---
KB_ENABLED = os.getenv("KB_ENABLED", "true").lower() in ("1", "true", "yes", "on")
# 知识库目录（相对项目根或绝对路径），该目录随代码仓库一起提交
KB_DIR = os.getenv("KB_DIR", "knowledge_base")
KB_CHUNK_SIZE = int(os.getenv("KB_CHUNK_SIZE", "600"))
KB_CHUNK_OVERLAP = int(os.getenv("KB_CHUNK_OVERLAP", "80"))
KB_TOP_K = int(os.getenv("KB_TOP_K", "3"))
KB_MIN_SCORE = float(os.getenv("KB_MIN_SCORE", "0.12"))


def get_project_root() -> str:
    """返回项目根目录绝对路径，保证所有模块在任何入口下都一致。"""
    return PROJECT_ROOT


def get_kb_abs_path() -> str:
    """返回知识库目录绝对路径；已随仓库一起提交，只读访问。"""
    if os.path.isabs(KB_DIR):
        return KB_DIR
    return os.path.join(PROJECT_ROOT, KB_DIR)


def is_deepseek_key_configured() -> bool:
    """检查 DeepSeek API Key 是否已正确配置（非空、非占位符）。"""
    key = DEEPSEEK_API_KEY.strip()
    if not key:
        return False
    if key.startswith("请在此") or key.startswith("your_") or "placeholder" in key.lower():
        return False
    return True
