# API reference

Base URL: `http://localhost:5000/api` (dev) or your deployed backend.

Errors: `{ "error": "<code>", "message": "<human text>" }`

---

## Health & config

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | `{ status, papers }` |
| GET | `/config` | LLM provider status, search modes, discovery sources |

---

## Papers — ingest

| Method | Path | Body / params | Description |
|--------|------|---------------|-------------|
| POST | `/papers/upload` | `multipart file` | Upload PDF (max 25 MB). Returns `202` + paper id; poll status. |
| GET | `/papers` | `?status=ready` | List library |
| GET | `/papers/{id}` | | Full metadata, sections, keywords, cached summary |
| GET | `/papers/{id}/status` | | `queued` → `processing` → `ready` / `failed` |
| DELETE | `/papers/{id}` | | Remove from DB, FAISS, BM25 |
| GET | `/papers/arxiv/search` | `?q=` | Top 10 arXiv hits (pick one to import) |
| POST | `/papers/import-arxiv` | `{ "arxiv_id": "..." }` or `{ "query": "..." }` | Import by ID or return search picks |
| POST | `/papers/discover` | `{ "query", "sources": ["arxiv","openalex","semantic_scholar"], "max_per_source": 15 }` | Search many catalogs at once |
| POST | `/papers/import-bulk` | `{ "items": [...], "delay_sec": 1.5 }` | Queue up to 200 imports (background) |

**Bulk item shape** (any of):

```json
{ "arxiv_id": "1706.03762" }
{ "openalex_id": "W2741809807" }
{ "pdf_url": "https://...", "title": "...", "authors": "...", "doi": "..." }
```

---

## Search

| Method | Path | Params |
|--------|------|--------|
| GET | `/search` | `q`, `mode=hybrid\|semantic\|keyword`, `k`, `section`, `year`, `year_from`, `year_to`, `author`, `page`, `page_size` |

---

## AI (Gemini when `LLM_PROVIDER=gemini`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/papers/{id}/summarize` | `?regenerate=true` optional. JSON summary fields. |
| POST | `/qa` | `{ "question", "paper_id? }` — RAG answer + sources |
| GET | `/qa/stream` | SSE: `?question=&paper_id=` |
| POST | `/qa` + `stream: true` | Same SSE via POST body |
| GET | `/qa/history` | `?paper_id=` |
| GET | `/papers/{id}/similar` | Top 5 by embedding similarity |
| GET | `/papers/{id}/keywords` | KeyBERT keywords |
| GET | `/topics` | Library clusters + 2D plot points |
| POST | `/compare` | `{ "paper_ids": [a, b] }` |

Without an API key, summarize/compare use extractive fallbacks; Q&A returns retrieved chunks.

---

## Example: discover + bulk import

```bash
curl -X POST http://localhost:5000/api/papers/discover \
  -H "Content-Type: application/json" \
  -d '{"query":"dense retrieval transformers","max_per_source":20}'

curl -X POST http://localhost:5000/api/papers/import-bulk \
  -H "Content-Type: application/json" \
  -d '{"items":[{"arxiv_id":"2104.08663"},{"pdf_url":"https://..."}]}'
```
