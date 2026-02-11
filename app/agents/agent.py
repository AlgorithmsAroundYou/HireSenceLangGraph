
from langgraph.graph import StateGraph, MessagesState
from langchain_openai import ChatOpenAI
from app.core.config import settings
from langchain_community.llms import Ollama
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool

def _build_openai_llm():
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
    )


def _build_deepseek_llm():
    # Assuming DeepSeek exposes an OpenAI-compatible API
    return Ollama(
        model=settings.llm_model,
        temperature=0.5,
        # api_key=settings.deepseek_api_key or settings.openai_api_key,
        base_url=settings.deepseek_base_url,
    )

def _build_mistral_llm():
    # Assuming Mistral is exposed via an OpenAI-compatible HTTP API
    return Ollama(
        model=settings.llm_model,
        temperature=0.5,
        #api_key=settings.mistral_api_key,
        base_url=settings.mistral_base_url,
    )


def build_llm():
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return _build_openai_llm()
    if provider == "deepseek":
        return _build_deepseek_llm()
    if provider == "mistral":
        return _build_mistral_llm()
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")


@tool
def add(a: int, b: int) -> int:
    """Adds two numbers together and returns the sum."""
    return a + b

# List of tools to pass to the agent
tools = [add]

def build_agent():
    llm = build_llm()

    def call_model(state: MessagesState):
        response = llm.invoke(state["messages"])
        return {"messages": state["messages"] + [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.set_entry_point("agent")
    graph.set_finish_point("agent")

    return graph.compile()
