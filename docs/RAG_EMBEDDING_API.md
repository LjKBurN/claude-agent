# RAG Embedding API 文档 — 智谱 AI

本文档描述 RAG 系统所需的 Embedding API 接口及其在知识库构建和检索中的使用方式。

---

## 1. API 概述

### 接口地址

```
POST https://open.bigmodel.cn/api/paas/v4/embeddings
```

### 认证方式

请求头携带 API Key：
```
Authorization: Bearer <your_api_key>
Content-Type: application/json
```

### 推荐模型

| 模型 | 向量维度 | 单条最大 Tokens | 适用场景 |
|------|----------|-----------------|----------|
| `embedding-3` | 2048（可自定义：256/512/1024/2048） | 3072 | **推荐**，语义理解更强，支持灵活维度 |
| `embedding-2` | 1024（固定） | 512 | 旧版，兼容场景 |

**建议使用 `embedding-3` + `dimensions: 1024`**，在精度和性能之间取得平衡。

---

## 2. RAG 中需要调用的接口

RAG 全流程只需要**一个接口**：`/v4/embeddings`，在两个阶段分别使用：

```
┌──────────────────────────────────────────────────────────┐
│                    /v4/embeddings                         │
│                                                          │
│  阶段一：知识库构建（批量）                                │
│  文档分块 → 批量 Embedding → 存入向量数据库                │
│                                                          │
│  阶段二：在线检索（单条）                                  │
│  用户查询 → 单条 Embedding → 向量相似度搜索                │
└──────────────────────────────────────────────────────────┘
```

---

## 3. 请求参数

### 请求体 (Request Body)

```json
{
    "model": "embedding-3",
    "input": "需要向量化的文本内容",
    "dimensions": 1024
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `model` | `string` | 是 | 模型名称：`embedding-2` 或 `embedding-3` |
| `input` | `string` 或 `string[]` | 是 | 输入文本，支持单条或数组批量 |
| `dimensions` | `integer` | 否 | 输出向量维度（仅 embedding-3），可选：256、512、1024、2048 |

### `input` 参数限制

- **embedding-2**：单条最多 512 Tokens，数组总长度 ≤ 8K Tokens
- **embedding-3**：单条最多 3072 Tokens，数组总长度上限更高

### `dimensions` 可选值（仅 embedding-3）

| 维度 | 适用场景 |
|------|----------|
| `2048` | 默认值，最高精度，适合对准确性要求极高的场景 |
| `1024` | **推荐**，精度与性能平衡，适合通用 RAG |
| `512` | 较高性能，适合大规模粗筛 |
| `256` | 最快速度，适合初步筛选后精排 |

> embedding-2 固定输出 1024 维，不支持 dimensions 参数。

---

## 4. 响应参数

### 响应体 (Response Body)

```json
{
    "model": "embedding-3",
    "object": "list",
    "data": [
        {
            "object": "embedding",
            "index": 0,
            "embedding": [0.023, -0.041, 0.087, ..., 0.012]
        },
        {
            "object": "embedding",
            "index": 1,
            "embedding": [-0.015, 0.032, -0.078, ..., 0.041]
        }
    ],
    "usage": {
        "prompt_tokens": 100,
        "completion_tokens": 0,
        "total_tokens": 100
    }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `model` | `string` | 使用的模型名称 |
| `object` | `string` | 固定值 `"list"` |
| `data` | `array` | 嵌入结果数组，与输入顺序一一对应 |
| `data[].object` | `string` | 固定值 `"embedding"` |
| `data[].index` | `integer` | 对应 `input` 数组中的索引 |
| `data[].embedding` | `float[]` | 向量数据，维度由 `dimensions` 参数决定 |
| `usage.prompt_tokens` | `integer` | 输入消耗的 token 数 |
| `usage.total_tokens` | `integer` | 总消耗的 token 数 |

---

## 5. 在项目中的使用方式

### 5.1 阶段一：知识库构建（批量 Embedding）

文档上传后，解析→分块→批量向量化：

```python
import httpx

EMBEDDING_API_URL = "https://open.bigmodel.cn/api/paas/v4/embeddings"
EMBEDDING_MODEL = "embedding-3"
EMBEDDING_DIMENSIONS = 1024
BATCH_SIZE = 50  # 每批最多 50 条分块

async def embed_chunks(
    chunks: list[str],
    api_key: str,
    batch_size: int = BATCH_SIZE,
) -> list[list[float]]:
    """将文档分块批量向量化。

    Args:
        chunks: 文档分块文本列表
        api_key: 智谱 API Key
        batch_size: 每批处理数量

    Returns:
        与 chunks 顺序对应的向量列表
    """
    all_embeddings: list[list[float]] = []

    async with httpx.AsyncClient(timeout=60) as client:
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            resp = await client.post(
                EMBEDDING_API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": EMBEDDING_MODEL,
                    "input": batch,
                    "dimensions": EMBEDDING_DIMENSIONS,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            # 按 index 排序确保顺序一致
            sorted_data = sorted(data["data"], key=lambda x: x["index"])
            all_embeddings.extend([item["embedding"] for item in sorted_data])

    return all_embeddings
```

**调用时机**：
- 用户上传文档 → 后台任务解析分块 → 调用 `embed_chunks()` → 存入向量数据库

### 5.2 阶段二：在线检索（查询 Embedding）

用户发消息时，将查询文本向量化后检索：

```python
async def embed_query(query: str, api_key: str) -> list[float]:
    """将用户查询向量化（单条）。"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            EMBEDDING_API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": EMBEDDING_MODEL,
                "input": query,
                "dimensions": EMBEDDING_DIMENSIONS,
            },
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]
```

**调用时机**：
- Agent 调用 `knowledge_search` 工具 → 调用 `embed_query()` → 向量数据库 Top-K 检索

### 5.3 完整检索流程

```python
async def knowledge_search(
    query: str,
    kb_ids: list[str],
    api_key: str,
    top_k: int = 5,
) -> list[dict]:
    """从知识库检索相关文档片段。

    Args:
        query: 用户查询文本
        kb_ids: 要检索的知识库 ID 列表
        api_key: 智谱 API Key
        top_k: 返回最相关的 K 个结果

    Returns:
        [{"content": "文档片段", "score": 0.92, "doc_name": "xxx.pdf", ...}]
    """
    # 1. 查询向量化
    query_vector = await embed_query(query, api_key)

    # 2. 向量数据库检索（按 kb_ids 过滤）
    results = vector_db.search(
        vector=query_vector,
        top_k=top_k,
        filter={"kb_id": {"$in": kb_ids}},
    )

    # 3. 返回结果
    return [
        {
            "content": r["content"],
            "score": r["score"],
            "doc_name": r["metadata"]["doc_name"],
            "chunk_index": r["metadata"]["chunk_index"],
        }
        for r in results
    ]
```

---

## 6. 配置项

需要在 `backend/config.py` 中新增的配置：

```python
# RAG / Embedding 配置
ZHIPU_API_KEY: str = ""                          # 智谱 API Key
ZHIPU_EMBEDDING_MODEL: str = "embedding-3"        # Embedding 模型
ZHIPU_EMBEDDING_DIMENSIONS: int = 1024            # 向量维度
ZHIPU_EMBEDDING_BATCH_SIZE: int = 50              # 批量向量化每批数量
RAG_CHUNK_SIZE: int = 500                         # 文档分块大小（字符）
RAG_CHUNK_OVERLAP: int = 50                       # 分块重叠字符数
RAG_TOP_K: int = 5                                # 检索返回结果数
```

对应环境变量：

```bash
ZHIPU_API_KEY=your-zhipu-api-key
ZHIPU_EMBEDDING_MODEL=embedding-3
ZHIPU_EMBEDDING_DIMENSIONS=1024
```

---

## 7. SDK 调用（可选）

除 HTTP 直接调用外，也可使用智谱官方 Python SDK：

```bash
pip install zai-sdk
```

```python
from zai import ZhipuAiClient

client = ZhipuAiClient(api_key="your-api-key")

# 批量向量化
response = client.embeddings.create(
    model="embedding-3",
    input=["文本1", "文本2", "文本3"],
)
for item in response.data:
    print(f"index={item.index}, dim={len(item.embedding)}")
```

> **注意**：SDK 是同步调用，在 FastAPI 异步环境中需用 `asyncio.to_thread()` 包装，或直接使用 HTTP 异步调用（推荐 5.1/5.2 节的方式）。

---

## 8. 错误处理

| HTTP 状态码 | 含义 | 处理方式 |
|-------------|------|----------|
| `401` | API Key 无效 | 检查配置 |
| `429` | 请求频率超限 | 指数退避重试 |
| `400` | 参数错误（如 input 超 token 限制） | 减小分块大小或批量数 |
| `500` | 服务端错误 | 重试 |

建议实现重试逻辑（参考项目中 `anthropic_provider.py` 的重试模式）：

```python
import asyncio

MAX_RETRIES = 3

async def embed_with_retry(chunks, api_key, batch_size=BATCH_SIZE):
    for attempt in range(MAX_RETRIES):
        try:
            return await embed_chunks(chunks, api_key, batch_size)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < MAX_RETRIES - 1:
                wait = 2 ** attempt
                logger.warning(f"Rate limited, retrying in {wait}s")
                await asyncio.sleep(wait)
            else:
                raise
```

---

## 参考链接

- [智谱 AI 文本嵌入 API Reference](https://docs.bigmodel.cn/api-reference/%E6%A8%A1%E5%9E%8B-api/%E6%96%87%E6%9C%AC%E5%B5%8C%E5%85%A5)
- [Embedding-3 模型说明](https://docs.bigmodel.cn/cn/guide/models/embedding/embedding-3)
- [Embedding-2 模型说明](https://docs.bigmodel.cn/cn/guide/models/embedding/embedding-2)
- [OpenAI 兼容迁移指南](https://docs.bigmodel.cn/cn/guide/platform/model-migration)
