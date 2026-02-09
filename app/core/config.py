from pydantic import BaseModel
import os
from dotenv import load_dotenv

# Load variables from .env if present
load_dotenv()


class Settings(BaseModel):
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


settings = Settings()
