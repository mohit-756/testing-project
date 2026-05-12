import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables once at startup
load_dotenv()

class Config:
    # Environment and CORS
    ENV = os.getenv("ENV", "development").strip().lower()
    DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", DEFAULT_ORIGINS)

    # Security
    # CRITICAL: No default SECRET_KEY - must be set in environment variables
    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY and ENV == "production":
        raise ValueError("SECRET_KEY must be set in environment variables for production. Run: openssl rand -hex 32")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))

    # Upload limits
    MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))

    # Google OAuth
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")

    # Communication (Email)
    EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

    # LLM Provider Configuration
    # Supported providers: openai, gemini, groq, cerebras, ollama
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip()
    LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
    LLM_MODEL_PRIMARY = os.getenv("LLM_MODEL_PRIMARY", "").strip()
    LLM_MODEL_FALLBACK = os.getenv("LLM_MODEL_FALLBACK", "").strip()
    
    # Specific Health Check / Provider settings
    OLLAMA_CHAT_URL = os.getenv("OLLAMA_CHAT_URL", "http://localhost:11434/api/chat").strip()
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b").strip()
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")

    # Frontend Integration
    # Standardizing cleanup of URLs (fixing potential typos like 'https ://')
    raw_frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").strip()
    FRONTEND_URL = raw_frontend_url.replace(" ", "") if "https" in raw_frontend_url else raw_frontend_url

    # Interview scheduling and access windows
    INTERVIEW_DEFAULT_TIMEZONE = os.getenv("INTERVIEW_DEFAULT_TIMEZONE", "Asia/Kolkata").strip()
    INTERVIEW_START_EARLY_MINUTES = int(os.getenv("INTERVIEW_START_EARLY_MINUTES", "10"))
    INTERVIEW_START_LATE_GRACE_MINUTES = int(os.getenv("INTERVIEW_START_LATE_GRACE_MINUTES", "30"))

    # ElevenLabs TTS Configuration (disabled - using browser TTS fallback)
    # ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()

    # Paths
    BASE_DIR = Path(__file__).resolve().parent.parent
    UPLOAD_DIR = BASE_DIR / "uploads"

    # S3 Configuration (for proctoring, PDF, and Polly TTS via Lambda)
    LAMBDA_S3_URL = os.getenv("LAMBDA_S3_URL", "https://lp6t2xn0q4.execute-api.ap-south-1.amazonaws.com/prod/generate-upload-url")
    S3_PROCTOR_PREFIX = os.getenv("S3_PROCTOR_PREFIX", "proctoring")
    S3_REPORT_PREFIX = os.getenv("S3_REPORT_PREFIX", "reports")

# Instantiate for global use
config = Config()
