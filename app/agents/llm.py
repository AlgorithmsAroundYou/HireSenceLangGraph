from langchain_openai import ChatOpenAI
from langchain_community.llms import Ollama

from app.core.config import settings


def _build_openai_llm():
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
    )


def _build_deepseek_llm():
    """Build an LLM client for DeepSeek (OpenAI-compatible endpoint)."""
    return Ollama(
        model=settings.llm_model,
        temperature=0.5,
        base_url=settings.deepseek_base_url,
    )


def _build_mistral_llm():
    """Build an LLM client for Mistral (OpenAI-compatible endpoint)."""
    return Ollama(
        model=settings.llm_model,
        temperature=0.5,
        base_url=settings.mistral_base_url,
    )


def build_llm():
    """Return an LLM instance based on LLM_PROVIDER in settings."""
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return _build_openai_llm()
    if provider == "deepseek":
        return _build_deepseek_llm()
    if provider == "mistral":
        return _build_mistral_llm()
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
