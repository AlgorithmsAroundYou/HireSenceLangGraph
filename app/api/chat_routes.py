from fastapi import APIRouter, Depends
from langchain_core.messages import HumanMessage

from app.agents.agent import build_agent
from app.models.user import User
from app.models.api import ChatRequest, ChatResponse
from app.services.auth_service import get_current_user


router = APIRouter()
agent = build_agent()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user: User = Depends(get_current_user)):
    result = agent.invoke({"messages": [HumanMessage(content=request.message)]})
    last_message = result["messages"][-1]
    return ChatResponse(response=last_message.content)
