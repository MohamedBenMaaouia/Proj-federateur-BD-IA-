# Vector database choice: Qdrant vs Milvus vs pgvector

## Context

The assistant answers questions from two kinds of content:

- **Owner's manuals** (English + French): long narrative text, where questions are matched by **meaning**, often across languages.
- **OBD-II diagnostic codes**: short records such as `P0420 — Catalyst System Efficiency Below Threshold (Bank 1)`, where questions must be matched on the **exact identifier**.

Embedding models represent codes like `P0420` and `P0455` as almost identical vectors, so dense search alone can't reliably find the right code. The database must therefore support **hybrid search**: dense vectors for meaning plus sparse BM25 vectors for exact terms, fused into one ranking. It must also filter by metadata (language, document type) and run easily on a developer laptop.

## Evaluation criteria

| # | Criterion | Why it matters here |
|---|---|---|
| 1 | **Metadata filtering** | Restrict a search to one language or document type (e.g. French manual chunks only), without losing results the way post-filtering does |
| 2 | **Latency** | Retrieval sits on every question's critical path, before the LLM starts generating |
| 3 | **Local orchestration simplicity** | Developers and CI must start the database with one command |
| 4 | **Native hybrid search** | Exact matching of diagnostic codes is a core requirement |
| 5 | **LangChain integration** | The orchestration layer is LangChain |
| 6 | **Path to production** | The same API should work from a laptop to a server |

## Comparison

### Qdrant

- **Filtering:** payload filters (exact match, lists, ranges, combinations) are applied *during* the HNSW search, with payload indexes on filtered fields. Filtered queries keep their recall instead of losing results after the fact.
- **Hybrid search:** each point stores **named dense and sparse vectors**. The Query API runs both searches as prefetches and fuses them with **Reciprocal Rank Fusion in a single request**. The sparse vector supports an **IDF modifier**, so the BM25 weighting is computed by the database.
- **Latency:** written in Rust and built specifically for vector search (HNSW, optional quantization). It's low at our scale, and will be measured on our corpus.
- **Local orchestration:** **one container** (`qdrant/qdrant`), plus an embedded mode for tests with no server at all. A web dashboard is included.
- **LangChain:** `langchain-qdrant`, with dense, sparse and hybrid retrieval modes.
- **Production:** the same API on a single server or a cluster, with replication, snapshots and quantization.

### Milvus

- **Filtering:** scalar fields with boolean filter expressions, applied during the search.
- **Hybrid search:** supported natively in recent versions (sparse vectors, multi-vector search, RRF and weighted reranking).
- **Latency:** excellent, especially at very large scale (hundreds of millions to billions of vectors), with GPU index options.
- **Local orchestration:** the standalone deployment needs **three services** (Milvus, etcd for metadata, MinIO for storage). A lightweight embedded variant (Milvus Lite) exists, but with a reduced feature set.
- **LangChain:** `langchain-milvus`.
- **Production:** distributed, cloud-native architecture; it shines at a scale this project doesn't have.

### pgvector (PostgreSQL)

- **Filtering:** the full power of SQL `WHERE`, joins and relational constraints.
- **Hybrid search:** **no native BM25.** Keyword search would use PostgreSQL full-text search (`tsvector` / `ts_rank`), which ranks differently from BM25, and the fusion with vector results must be written by hand in SQL or in the application. Extensions such as `pg_search` add BM25, but they're an extra dependency.
- **Latency:** good with HNSW indexes at small and medium scale, but vector search shares resources with the relational workload.
- **Local orchestration:** one PostgreSQL container, plus enabling the extension and managing tables and indexes.
- **LangChain:** `langchain-postgres`.
- **Production:** inherits PostgreSQL operations (backups, replicas), an advantage when an organization already runs Postgres.

## Summary

| Criterion | Qdrant | Milvus | pgvector |
|---|---|---|---|
| Metadata filtering | ✅ during search, indexed | ✅ during search | ✅ SQL |
| Native hybrid (dense + BM25) | ✅ one query, RRF | ✅ | ⚠️ no native BM25 |
| Latency at our scale | ✅ low | ✅ low | ✅ good |
| Local orchestration | ✅ 1 container | ❌ 3 services | ✅ 1 container + setup |
| LangChain integration | ✅ incl. hybrid mode | ✅ | ✅ |
| Fit for this project | **best** | over-sized | workable, more custom code |

## Decision: Qdrant

1. **Hybrid search is native and simple.** Dense and BM25 vectors live on the same point and are fused by RRF in one query, with no second keyword index to keep in sync. This directly addresses exact diagnostic-code lookups.
2. **Filtering during the search.** Language and document-type filters are applied inside the vector search, backed by payload indexes.
3. **One container locally**, with the same API up to a server or cluster deployment.

**Rejected alternatives.** **Milvus** would be the choice at hundreds of millions of vectors, but its three-service local stack adds operational weight for no benefit at our scale (a few thousand chunks). **pgvector** would be preferred if the project already ran on PostgreSQL, but the lack of native BM25 means building and maintaining hybrid fusion ourselves.

## Planned collection design

| Element | Configuration |
|---|---|
| Dense vector `dense` | multilingual sentence-embedding model, cosine distance |
| Sparse vector `bm25` | FastEmbed `Qdrant/bm25`, `modifier = IDF` |
| Payload | `page_content`, `metadata.source`, `metadata.page`, `metadata.doc_type`, `metadata.language`, `metadata.chunk_id` |
| Payload indexes | `metadata.language`, `metadata.doc_type` (keyword) |
| Query | prefetch dense + prefetch sparse → RRF fusion → reranker |

Latency will be measured on the project's own corpus with the evaluation harness, rather than taken from vendor benchmarks.
