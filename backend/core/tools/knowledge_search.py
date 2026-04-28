"""知识库语义检索工具 — Agent 可调用。"""

from __future__ import annotations

import logging

from backend.core.tools.base import register_tool

logger = logging.getLogger(__name__)


@register_tool(
    name="knowledge_search",
    description=(
        "Search knowledge bases for relevant document fragments using semantic similarity. "
        "Returns the most relevant text chunks along with their source document names and "
        "similarity scores. Use this tool when you need to retrieve information from the "
        "user's uploaded documents or knowledge bases."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query text to find relevant information.",
            },
            "knowledge_base_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of knowledge base IDs to search in.",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of top results to return (default: 5).",
            },
        },
        "required": ["query", "knowledge_base_ids"],
    },
)
async def knowledge_search(arguments: dict) -> str:
    """语义检索知识库。"""
    query = arguments["query"]
    kb_ids = arguments["knowledge_base_ids"]
    top_k = arguments.get("top_k", 5)

    from backend.config import get_settings

    settings = get_settings()
    if not settings.zhipu_api_key:
        return "Error: ZHIPU_API_KEY 未配置，无法进行语义搜索"

    try:
        from backend.core.rag.embedding import get_embedding_service
        from backend.core.rag.vector_store import get_vector_store
        from backend.db.database import async_session

        # 查询向量化
        embedding_service = get_embedding_service()
        query_embedding = await embedding_service.embed_query(query)

        # 向量检索
        vector_store = get_vector_store()
        async with async_session() as db:
            results = await vector_store.search(
                query_embedding=query_embedding,
                kb_ids=kb_ids,
                top_k=top_k,
                db=db,
            )
    except Exception as e:
        logger.exception("知识库检索失败")
        return f"Error: 检索失败 - {e}"

    if not results:
        return "未找到相关结果。知识库可能尚未完成向量化，或查询与文档内容不相关。"

    # 格式化输出
    parts = []
    for i, r in enumerate(results, 1):
        header = f"[{i}] {r.document_title}"
        if r.section_headers:
            header += f" > {' > '.join(r.section_headers)}"
        header += f" (score: {r.score:.3f})"
        parts.append(f"{header}\n{r.content}")

    return "\n\n---\n\n".join(parts)
