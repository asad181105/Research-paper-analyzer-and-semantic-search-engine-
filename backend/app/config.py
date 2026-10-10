import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (parent of backend/) then backend/
_root = Path(__file__).resolve().parents[2]
load_dotenv(_root / ".env")
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


def _bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    DATA_DIR = Path(os.getenv("DATA_DIR", str(_root / "data"))).resolve()
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{(DATA_DIR / 'papers.db').as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024

    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    CITATION_WEIGHT = float(os.getenv("CITATION_WEIGHT", "0.15"))
    RELEVANCE_WEIGHT = float(os.getenv("RELEVANCE_WEIGHT", "0.85"))

    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "llama3.1")
    SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    LLM_RATE_LIMIT = os.getenv("LLM_RATE_LIMIT", "10/minute")

    CHUNK_TOKENS = int(os.getenv("CHUNK_TOKENS", "300"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
    DEBUG = _bool("FLASK_DEBUG", os.getenv("FLASK_ENV", "development") == "development")

    @classmethod
    def ensure_dirs(cls) -> None:
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        (cls.DATA_DIR / "uploads").mkdir(parents=True, exist_ok=True)
        (cls.DATA_DIR / "indexes").mkdir(parents=True, exist_ok=True)
