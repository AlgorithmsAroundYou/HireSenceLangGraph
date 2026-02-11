from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import ToolNode

from app.agents.llm import build_llm
from app.agents.tools import TOOLS
from app.prompts.resume_analysis_prompt import RESUME_ANALYSIS_SYSTEM_PROMPT
from langchain_core.messages import SystemMessage


def build_agent():
    llm = build_llm()

    def call_model(state: MessagesState):
        response = llm.invoke(state["messages"])
        return {"messages": state["messages"] + [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.set_entry_point("agent")
    graph.set_finish_point("agent")

    return graph.compile()


def build_resume_processing_agent():
    """Agent specialized for JD + resume analysis, seeded with a system prompt.

    Currently thin wrapper around the base LLM; can be extended with tools/memory.
    """

    llm = build_llm()

    def call_model(state: MessagesState):
        # Prepend resume analysis system prompt once at start
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=RESUME_ANALYSIS_SYSTEM_PROMPT)] + messages
        response = llm.invoke(messages)
        return {"messages": messages + [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    graph.set_entry_point("agent")
    graph.set_finish_point("agent")

    return graph.compile()
