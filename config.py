import os
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

JWT_SECRET = os.getenv("JWT_SECRET", "lakeeval-dev-secret")
JWT_EXPIRY_HOURS = 24

FLASK_PORT = int(os.getenv("FLASK_PORT", "5001"))
STREAMLIT_PORT = int(os.getenv("STREAMLIT_PORT", "8501"))
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")

DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///lake_eval.db")

DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")

# --- 游客限制 ---
GUEST_DAILY_CHAT_LIMIT = int(os.getenv("GUEST_DAILY_CHAT_LIMIT", "5"))
GUEST_MAX_TOKENS = int(os.getenv("GUEST_MAX_TOKENS", "500"))
GUEST_TOKEN_EXPIRY_HOURS = int(os.getenv("GUEST_TOKEN_EXPIRY_HOURS", "2"))

# --- 安全 ---
# CORS 白名单（逗号分隔），公网部署时改为你的前端域名
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "ALLOWED_ORIGINS",
        f"http://localhost:{STREAMLIT_PORT},http://127.0.0.1:{STREAMLIT_PORT}"
    ).split(",") if o.strip()
]
# 全局 IP 速率限制（每分钟请求数）
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

# --- 本地知识库 RAG ---
# 是否启用本地知识库（将 .txt/.md 文件内容注入 AI 回答上下文）
KB_ENABLED = os.getenv("KB_ENABLED", "true").lower() in ("1", "true", "yes", "on")
# 知识库目录（相对 LakeEval 项目根），可放多个 .txt/.md 文件
KB_DIR = os.getenv("KB_DIR", "knowledge_base")
# 单块最大字符数（按段落切分，超长再按长度切片）
KB_CHUNK_SIZE = int(os.getenv("KB_CHUNK_SIZE", "600"))
# 块重叠字符（避免切分丢失上下文）
KB_CHUNK_OVERLAP = int(os.getenv("KB_CHUNK_OVERLAP", "80"))
# 检索返回的最大块数
KB_TOP_K = int(os.getenv("KB_TOP_K", "3"))
# 最低相似度阈值（0~1，低于该值认为知识库无相关内容，不注入）
KB_MIN_SCORE = float(os.getenv("KB_MIN_SCORE", "0.12"))


def is_deepseek_key_configured() -> bool:
    """检查 DeepSeek API Key 是否已正确配置（非空、非占位符）。"""
    key = DEEPSEEK_API_KEY.strip()
    if not key:
        return False
    if key.startswith("请在此") or key.startswith("your_") or "placeholder" in key.lower():
        return False
    return True
