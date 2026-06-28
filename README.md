---
title: Rag Project Assistant
emoji: 🔥
colorFrom: red
colorTo: red
sdk: docker
pinned: false
short_description: RAG (Retrieval-Augmented Generation) system that answers que
---

![RAG pipeline illustration](https://github-production-user-asset-6210df.s3.amazonaws.com/119807029/614266694-16851bcf-1fb4-4b12-90a5-3d564329f510.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAVCODYLSA53PQK4ZA%2F20260628%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260628T154713Z&X-Amz-Expires=300&X-Amz-Signature=65a4e5c0594c3afdc1ca59d51d7423e09b2129b41dba5c37d2f9c1b386dceda9&X-Amz-SignedHeaders=host&response-content-type=image%2Fpng)

_Conceptual illustration — see [Demo](#demo) below for the actual terminal interface._

# frissonitte's rag project assistant

A local RAG (Retrieval-Augmented Generation) chatbot for querying personal project documentation. Built to replace hallucination-prone LLM responses with grounded answers extracted from actual project source code and documentation.

**Current state:** Fully deployed. FastAPI backend on Hugging Face Spaces (Docker), Groq inference (Llama 3.3 70B), IP-based rate limiting, and a vanilla JS chat widget embedded at [emirhanyildirim.me](https://emirhanyildirim.me). CLI mode still available locally.

## Roadmap

- [x] Replace Ollama with Groq API (Llama 3.3 70B) for cloud inference
- [x] Expose `/chat` POST endpoint via FastAPI
- [x] Add IP-based rate limiting (`slowapi`)
- [x] Deploy backend to Hugging Face Spaces (Docker SDK)
- [x] Build vanilla JS chat widget for portfolio site integration
- [x] Embed widget into [emirhanyildirim.me](https://emirhanyildirim.me) (Jekyll / GitHub Pages)

## Demo

![Actual chat interface](https://github-production-user-asset-6210df.s3.amazonaws.com/119807029/614279678-0ab59c97-020c-47df-a608-0c4f4e2f6e41.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAVCODYLSA53PQK4ZA%2F20260628%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260628T180403Z&X-Amz-Expires=300&X-Amz-Signature=e3e3fde80c3b024c1bf3c1a44867f5046c045b7d472ec11b3c3e87b357ad7aeb&X-Amz-SignedHeaders=host&response-content-type=image%2Fpng)
_Real terminal output: retrieved chunks with similarity scores, project filtering, and grounded answer generation._

## Architecture

```
documents/               ← prepared knowledge base
    ├── *_README.md      ← project README files
    ├── *_code_context.txt  ← AST-extracted code structure
    └── *_highlights.txt ← curated project summaries & rationale

prepare_docs.py          ← knowledge base builder
build_index.py           ← builds ChromaDB index (run at Docker build time)
rag_chatbot.py           ← retrieval + generation core (shared by CLI and API)
app.py                   ← FastAPI service (POST /query, rate limiting)
chroma_db/               ← persistent vector index
Dockerfile               ← multi-stage build, pre-builds index, exposes :7860
```

**Pipeline:**

1. `prepare_docs.py` extracts structured context from each project
2. `build_index.py` embeds chunks with `all-MiniLM-L6-v2` and stores in ChromaDB (runs at Docker build time)
3. At query time: project keyword detection → metadata-filtered retrieval → Groq generation with strict grounding prompt
4. Response includes `answer`, `sources` (list of source files), and `low_confidence` flag

## Document Extraction (`prepare_docs.py`)

Uses Python `ast` module (not regex) to extract per-file:

- Module, class, and function docstrings
- Function signatures with type annotations and return types
- `ALL_CAPS` module-level constants (configuration values)
- Inline comments
- `README.md` and `highlights.txt` copied as-is

Regex-based extraction was discarded because it misattributed multi-line string literals as docstrings and could not reconstruct function signatures reliably.

## Retrieval Design

**Embedding model:** `sentence-transformers/all-MiniLM-L6-v2`  
**Vector store:** ChromaDB (persistent, SQLite-backed)  
**Chunk size:** 200 words, 40-word overlap

**Similarity threshold:** L2 distance < 1.40 passes; above this a low-confidence warning is shown and the LLM is still invoked but the user is alerted. Threshold was calibrated empirically: `all-MiniLM-L6-v2` L2 distances in the 1.0–1.3 range correspond to topically related but not directly answering chunks; distances above 1.5 are typically off-topic.

**Project-scoped metadata filtering:** Each chunk is indexed with a `project` metadata field derived from its filename prefix. When a query mentions a known project by name or keyword, ChromaDB's `$eq` filter restricts retrieval to that project's chunks only. Without this, semantically similar chunks from other projects contaminate the context — e.g. a question about Listing Pilot's Telegram integration would retrieve WBC Analyzer's GPT-4o API discussion because both involve external API calls.

Fallback: if the filtered query returns no results (project has few chunks), the filter is dropped and a full-corpus search runs.

## Generation Prompt

```
You are an assistant that answers questions about the developer's own projects.
The context below comes from that project's documentation and source code.
Rules:
1. Answer using information present in the context, including reasonable direct
   inferences (e.g. if a table lists architectures tested, you can state which
   ones were used).
2. If the context genuinely contains no relevant information, say exactly:
   'I don't have this information.' and stop.
3. Do not invent facts not supported by the context.
4. Mention which project or file the information comes from.
5. Be concise and precise. Answer in the same language as the question.
```

## Knowledge Base Design

Two source types with different roles:

| Source              | Content                                                | Answers                                      |
| ------------------- | ------------------------------------------------------ | -------------------------------------------- |
| `_code_context.txt` | AST-extracted signatures, docstrings, constants        | Implementation questions ("how does X work") |
| `_highlights.txt`   | Curated summaries, design rationale, known limitations | Motivation questions ("why was X chosen")    |

`_highlights.txt` is hand-written per project. This is intentional: motivation and architectural decisions are rarely in source code comments. The system is a hybrid — automatic extraction for structure, curated content for rationale. This distinction matters: the system does not "understand" code; it retrieves the most relevant pre-extracted or pre-written text and grounds the LLM's response to it.

## Known Limitations

**Source attribution errors at chunk boundaries:** The LLM sometimes names the wrong file as the source when the relevant information spans a chunk boundary. The chunk metadata records the source file, but a function defined in `utils.py` may appear in a chunk whose surrounding text is from a runner script. Not critical for Q&A accuracy but worth noting if precise attribution is required.

**Keyword-based project detection:** Project filtering relies on a static keyword list. Misspelled project names or paraphrased references are not caught. A more robust approach would use semantic similarity against project name embeddings, but the current approach is sufficient for the intended use case.

**Cloud inference dependency:** Generation requires a valid `GROQ_API_KEY`. If the Groq API is unreachable, the endpoint returns 503.

**Rate limiting:** The public API is limited to 3 requests per hour per IP via `slowapi`. Intended for the portfolio widget use case — not suitable for bulk querying.

## Setup

```bash
pip install -r requirements.txt

# Set up API key
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

# Build knowledge base (run once, or when projects change)
python prepare_docs.py

# Build ChromaDB index
python build_index.py

# Start CLI chatbot
python rag_chatbot.py

# Or start FastAPI server
fastapi dev app.py
```

**LLM:** Groq API with `llama-3.3-70b-versatile`. Requires `GROQ_API_KEY` in `.env`.

## API

**Live endpoint:** `https://frissonitte-rag-project-assistant.hf.space/query`

```bash
curl -X POST https://frissonitte-rag-project-assistant.hf.space/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is WBC Analyzer?"}'
```

**Response:**

```json
{
    "answer": "...",
    "sources": ["wbc-analyzer_README.md"],
    "low_confidence": false
}
```

Rate limit: 3 requests/hour per IP.

## Commands

| Command    | Description                                               |
| ---------- | --------------------------------------------------------- |
| `/reindex` | Rebuild ChromaDB index from current `documents/` contents |
| `/info`    | Show active model, index size                             |
| `/help`    | List commands                                             |
| `/exit`    | Quit                                                      |

## Projects Covered

- **WBC Analyzer** — DenseNet121-based WBC classification with OOD adaptation pipeline
- **Scalable Kinematic Action Recognition for Industry 5.0** — End-to-end action recognition on 10GB motion-capture data with streaming drift detection
- **Listing Pilot** — Appium automation suite for C2C marketplace listing management
- **Popcorn Wagon** — Hybrid movie recommender (SVD + Annoy + TMDB)
- **Portal Cleaner Ultimate** — RPA desktop suite for ERP workflow automation
