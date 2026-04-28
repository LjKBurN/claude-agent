"""智谱 Embedding 服务 — 异步批量向量化。"""

from __future__ import annotations

import asyncio
import logging

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)

_API_URL = "https://open.bigmodel.cn/api/paas/v4/embeddings"
_MAX_RETRIES = 3


class EmbeddingService:
    """封装智谱 Embedding API 调用。"""

    def __init__(
        self,
        api_key: str,
        model: str = "embedding-3",
        dimensions: int = 1024,
        batch_size: int = 50,
    ):
        self._api_key = api_key
        self._model = model
        self._dimensions = dimensions
        self._batch_size = batch_size

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量向量化文本（自动分批、指数退避重试）。

        Returns:
            与 texts 顺序对应的向量列表。
        """
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        async with httpx.AsyncClient(timeout=60) as client:
            for i in range(0, len(texts), self._batch_size):
                batch = texts[i : i + self._batch_size]
                embeddings = await self._embed_batch_with_retry(client, batch)
                all_embeddings.extend(embeddings)

        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        """单条查询向量化。"""
        results = await self.embed_texts([query])
        return results[0]

    async def _embed_batch_with_retry(
        self, client: httpx.AsyncClient, texts: list[str]
    ) -> list[list[float]]:
        """带重试的批量向量化。"""
        for attempt in range(_MAX_RETRIES):
            try:
                return await self._embed_batch(client, texts)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < _MAX_RETRIES - 1:
                    wait = 2**attempt
                    logger.warning("Embedding 限流，%ds 后重试", wait)
                    await asyncio.sleep(wait)
                else:
                    raise
        return []  # unreachable

    async def _embed_batch(
        self, client: httpx.AsyncClient, texts: list[str]
    ) -> list[list[float]]:
        """执行单次批量 Embedding API 调用。"""
        payload: dict = {
            "model": self._model,
            "input": texts,
        }
        # embedding-3 支持 dimensions 参数
        if self._dimensions and self._model == "embedding-3":
            payload["dimensions"] = self._dimensions

        resp = await client.post(
            _API_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        # 按 index 排序确保顺序一致
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]


# ---------------------------------------------------------------------------
# 单例工厂
# ---------------------------------------------------------------------------

_instance: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """获取 EmbeddingService 单例。"""
    global _instance
    if _instance is None:
        settings = get_settings()
        if not settings.zhipu_api_key:
            raise ValueError("ZHIPU_API_KEY 未配置")
        _instance = EmbeddingService(
            api_key=settings.zhipu_api_key,
            model=settings.zhipu_embedding_model,
            dimensions=settings.zhipu_embedding_dimensions,
            batch_size=settings.zhipu_embedding_batch_size,
        )
    return _instance
