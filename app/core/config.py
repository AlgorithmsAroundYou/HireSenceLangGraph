from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

# Load variables from .env if present
load_dotenv()


class Settings(BaseSettings):
    # Which backend: "openai", "deepseek", or "mistral"
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")

    # Common model name
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

    # OpenAI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # DeepSeek / custom (OpenAI-compatible)
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")

    # Mistral / custom
    mistral_base_url: str = os.getenv("MISTRAL_BASE_URL", "")
    mistral_api_key: str = os.getenv("MISTRAL_API_KEY", "")

    # File upload configuration
    # Default: JDs go to uploaded_jds/, resumes to uploaded_resumes/
    upload_dir_jd: str = os.getenv("UPLOAD_DIR_JD", "uploaded_jds")
    upload_dir_resume: str = os.getenv("UPLOAD_DIR_RESUME", "uploaded_resumes")

    # Generic allowed extensions (for legacy/general uploads)
    allowed_extensions: str = os.getenv("ALLOWED_EXTENSIONS", "txt,pdf,doc,docx")

    # JD validation config from environment
    # Example: ALLOWED_JD_EXTENSIONS="txt,pdf,doc,docx"
    allowed_jd_extensions: str = os.getenv(
        "ALLOWED_JD_EXTENSIONS", "txt,pdf,doc,docx"
    )
    # Example: MAX_JD_FILE_SIZE_BYTES="10485760"  (10 MB)
    max_jd_file_size_bytes: int = int(
        os.getenv("MAX_JD_FILE_SIZE_BYTES", str(10 * 1024 * 1024))
    )

    # JWT Configuration
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Resume processing worker configuration
    resume_process_interval_seconds: int = int(
        os.getenv("RESUME_PROCESS_INTERVAL_SECONDS", "60")
    )
    resume_process_batch_size: int = int(
        os.getenv("RESUME_PROCESS_BATCH_SIZE", "10")
    )
    resume_process_max_parallel: int = int(
        os.getenv("RESUME_PROCESS_MAX_PARALLEL", "3")
    )

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
