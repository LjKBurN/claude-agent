"""会话管理 API 路由。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas import SessionInfo, SessionList, MessageInfo, MessageList
from backend.db.database import get_db
from backend.db.models import Session, Message
from backend.middleware.auth import verify_api_key

router = APIRouter()


@router.get("", response_model=SessionList)
async def list_sessions(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> SessionList:
    """获取会话列表。"""
    # 查询总数
    count_result = await db.execute(select(func.count(Session.id)))
    total = count_result.scalar() or 0

    # 查询会话
    result = await db.execute(
        select(Session)
        .order_by(Session.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    sessions = result.scalars().all()

    # 查询每个会话的消息数
    session_list = []
    for session in sessions:
        msg_count_result = await db.execute(
            select(func.count(Message.id)).where(Message.session_id == session.id)
        )
        msg_count = msg_count_result.scalar() or 0

        session_list.append(SessionInfo(
            id=session.id,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=msg_count,
        ))

    return SessionList(sessions=session_list, total=total)


@router.get("/{session_id}/messages", response_model=MessageList)
async def get_session_messages(
    session_id: str,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> MessageList:
    """获取会话的消息历史。"""
    # 检查会话是否存在
    session_result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    if not session_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found")

    # 查询总数
    count_result = await db.execute(
        select(func.count(Message.id)).where(Message.session_id == session_id)
    )
    total = count_result.scalar() or 0

    # 查询消息
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
        .limit(limit)
        .offset(offset)
    )
    messages = result.scalars().all()

    return MessageList(
        messages=[
            MessageInfo(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
            )
            for msg in messages
        ],
        total=total,
    )


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """删除会话及其消息。"""
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.delete(session)
    await db.commit()

    return {"status": "deleted", "session_id": session_id}
