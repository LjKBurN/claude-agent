"""RAG 检索质量评测脚本。

用法:
    python -m tests.rag.eval_retrieval
    python -m tests.rag.eval_retrieval --top-k 5          # 自定义 top_k
    python -m tests.rag.eval_retrieval --threshold 0.5    # score 阈值过滤
    python -m tests.rag.eval_retrieval --dataset my_dataset.json  # 自定义评测集

指标说明:
    - Recall@K: 前 K 个检索结果中是否包含目标 chunk（命中率）
    - MRR:      第一个命中目标 chunk 的排名倒数（排序质量）
    - Keyword Hit: 检索结果中是否包含预期关键词
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from backend.core.rag.embedding import get_embedding_service
from backend.core.rag.vector_store import get_vector_store
from backend.db.database import async_session

# 默认评测集路径
DEFAULT_DATASET = Path(__file__).parent / "eval_dataset.json"

# 知识库 ID（从数据库查询获得，脚本启动时自动填充）
_kb_ids: list[str] = []


async def _load_kb_ids() -> list[str]:
    """从数据库加载所有知识库 ID。"""
    from sqlalchemy import text

    async with async_session() as db:
        result = await db.execute(text("SELECT id FROM knowledge_bases"))
        return [row.id for row in result.fetchall()]


async def _load_chunk_index_map() -> dict[int, str]:
    """加载 chunk_index → chunk_id 的映射（用于评测命中判定）。"""
    from sqlalchemy import text

    async with async_session() as db:
        result = await db.execute(
            text("SELECT id, chunk_index FROM document_chunks ORDER BY chunk_index")
        )
        return {row.chunk_index: row.id for row in result.fetchall()}


async def evaluate(
    dataset: list[dict],
    top_k: int = 3,
    score_threshold: float = 0.0,
    kb_ids: list[str] | None = None,
) -> dict:
    """运行检索评测。

    Args:
        score_threshold: 相似度阈值，低于此值的结果被过滤掉。
                         无关问题期望过滤后无结果，相关问题仅统计高于阈值的结果。

    Returns:
        评测结果字典，包含整体指标和每条样本的详细结果。
    """
    if not kb_ids:
        kb_ids = await _load_kb_ids()
    if not kb_ids:
        print("错误: 数据库中没有知识库")
        return {}

    chunk_map = await _load_chunk_index_map()
    embedding_service = get_embedding_service()
    vector_store = get_vector_store()

    results = []
    total_latency = 0.0

    threshold_str = f" | threshold={score_threshold}" if score_threshold > 0 else ""
    print(f"\n{'='*60}")
    print(f"RAG 检索评测 | top_k={top_k} | 样本数={len(dataset)} | 知识库={len(kb_ids)}{threshold_str}")
    print(f"{'='*60}\n")

    for item in dataset:
        qid = item["id"]
        question = item["question"]
        expected_indices = item["expected_chunk_indices"]
        expected_keywords = item["expected_keywords"]
        category = item.get("category", "")
        difficulty = item.get("difficulty", "")

        # 计时：embedding + search
        t0 = time.perf_counter()
        query_embedding = await embedding_service.embed_query(question)
        async with async_session() as db:
            search_results = await vector_store.search(
                query_embedding=query_embedding,
                kb_ids=kb_ids,
                top_k=top_k,
                db=db,
            )
        latency = time.perf_counter() - t0
        total_latency += latency

        # Score 阈值过滤
        filtered_results = (
            [r for r in search_results if r.score >= score_threshold]
            if score_threshold > 0
            else search_results
        )

        # 判定：Retrieval 命中
        retrieved_ids = {r.chunk_id for r in filtered_results}
        expected_ids = {chunk_map[idx] for idx in expected_indices if idx in chunk_map}

        hit = bool(retrieved_ids & expected_ids) if expected_ids else not retrieved_ids

        # MRR 计算
        mrr = 0.0
        if expected_ids:
            for rank, r in enumerate(filtered_results, 1):
                if r.chunk_id in expected_ids:
                    mrr = 1.0 / rank
                    break

        # 判定：关键词命中
        keyword_hits = 0
        if expected_keywords:
            all_content = " ".join(r.content for r in filtered_results)
            keyword_hits = sum(1 for kw in expected_keywords if kw in all_content)
            keyword_rate = keyword_hits / len(expected_keywords)
        else:
            keyword_rate = 1.0 if not retrieved_ids else 0.0

        # 过滤前后的数量用于展示
        n_before = len(search_results)
        n_after = len(filtered_results)

        results.append({
            "id": qid,
            "question": question,
            "category": category,
            "difficulty": difficulty,
            "hit": hit,
            "mrr": mrr,
            "keyword_rate": keyword_rate,
            "latency_ms": round(latency * 1000, 1),
            "scores": [round(r.score, 4) for r in search_results],
            "filtered_count": f"{n_after}/{n_before}",
            "retrieved_titles": [
                f"[chunk {r.chunk_index}] {r.document_title}" for r in filtered_results
            ],
        })

        # 实时输出
        status = "✓" if hit else "✗"
        print(
            f"  {status} #{qid:2d} [{category}] {question}\n"
            f"      命中={hit} MRR={mrr:.2f} 关键词={keyword_hits}/{len(expected_keywords)} "
            f"延迟={latency*1000:.0f}ms "
            f"scores={results[-1]['scores']}"
        )

    # ==================== 汇总 ====================
    n = len(results)
    recall = sum(1 for r in results if r["hit"]) / n
    avg_mrr = sum(r["mrr"] for r in results) / n
    avg_keyword_rate = sum(r["keyword_rate"] for r in results) / n
    avg_latency = total_latency / n * 1000

    # 按难度和类别分组统计
    by_difficulty = {}
    for r in results:
        d = r["difficulty"]
        by_difficulty.setdefault(d, {"hit": 0, "total": 0})
        by_difficulty[d]["total"] += 1
        if r["hit"]:
            by_difficulty[d]["hit"] += 1

    by_category = {}
    for r in results:
        c = r["category"]
        by_category.setdefault(c, {"hit": 0, "total": 0})
        by_category[c]["total"] += 1
        if r["hit"]:
            by_category[c]["hit"] += 1

    print(f"\n{'='*60}")
    print("汇总")
    print(f"{'='*60}")
    print(f"  Recall@{top_k}:    {recall:.1%} ({sum(1 for r in results if r['hit'])}/{n})")
    print(f"  MRR:              {avg_mrr:.3f}")
    print(f"  Keyword Hit Rate: {avg_keyword_rate:.1%}")
    print(f"  Avg Latency:      {avg_latency:.0f}ms")
    print()

    print("  按难度:")
    for d in ["easy", "medium", "hard"]:
        if d in by_difficulty:
            v = by_difficulty[d]
            print(f"    {d:6s}: {v['hit']}/{v['total']} = {v['hit']/v['total']:.1%}")

    print("\n  按类别:")
    for c, v in sorted(by_category.items()):
        print(f"    {c}: {v['hit']}/{v['total']} = {v['hit']/v['total']:.1%}")

    summary = {
        "top_k": top_k,
        "score_threshold": score_threshold,
        "total": n,
        "recall": recall,
        "mrr": avg_mrr,
        "keyword_rate": avg_keyword_rate,
        "avg_latency_ms": round(avg_latency, 1),
        "by_difficulty": {
            d: {"hit": v["hit"], "total": v["total"]}
            for d, v in by_difficulty.items()
        },
        "by_category": {
            c: {"hit": v["hit"], "total": v["total"]}
            for c, v in by_category.items()
        },
        "details": results,
    }
    return summary


def main():
    import argparse

    parser = argparse.ArgumentParser(description="RAG 检索质量评测")
    parser.add_argument(
        "--dataset", type=str, default=str(DEFAULT_DATASET),
        help="评测集 JSON 文件路径",
    )
    parser.add_argument("--top-k", type=int, default=3, help="检索 top_k (默认 3)")
    parser.add_argument(
        "--threshold", type=float, default=0.0,
        help="相似度阈值，低于此值的结果被过滤 (默认 0.0 不过滤)",
    )
    parser.add_argument(
        "--output", type=str, default="",
        help="评测结果输出文件路径（可选）",
    )
    args = parser.parse_args()

    with open(args.dataset) as f:
        dataset = json.load(f)

    result = asyncio.run(evaluate(
        dataset, top_k=args.top_k, score_threshold=args.threshold,
    ))

    if result and args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到 {args.output}")


if __name__ == "__main__":
    main()
