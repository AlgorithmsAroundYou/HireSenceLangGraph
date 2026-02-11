from langchain_core.tools import tool


@tool
def add(a: int, b: int) -> int:
    """Adds two numbers together and returns the sum."""
    return a + b


TOOLS = [add]
