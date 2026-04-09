"""聊天 API 路由。"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas import ChatRequest, ChatResponse
from backend.core.agent_service import agent_service
from backend.db.database import get_db
from backend.middleware.auth import verify_api_key

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> ChatResponse:
    """
    对话接口（非流式）。

    发送消息并获取 AI 响应。
    """
    return await agent_service.chat(
        user_message=request.message,
        session_id=request.session_id,
        db=db,
    )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    对话接口（流式 SSE）。

    发送消息并以 SSE 流式获取 AI 响应。

    事件类型：
    - session_id: 会话 ID
    - text: 文本片段
    - tool_start: 工具调用开始
    - tool_end: 工具调用结束
    - done: 完成
    """
    return StreamingResponse(
        agent_service.chat_stream(
            user_message=request.message,
            session_id=request.session_id,
            db=db,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
