---
title: Rag Project Assistant
emoji: 🔥
colorFrom: red
colorTo: red
sdk: docker
pinned: false
short_description: RAG (Retrieval-Augmented Generation) system that answers que
---

![RAG pipeline illustration](static/thumbnail.png)
_Conceptual illustration — see [Demo](#demo) below for the actual terminal interface._

# frissonitte's rag project assistant

A local RAG (Retrieval-Augmented Generation) chatbot for querying personal project documentation. Built to replace hallucination-prone LLM responses with grounded answers extracted from actual project source code and documentation.

**Current state:** FastAPI backend with Groq inference (Llama 3.3 70B). CLI mode still available locally. Planned deployment as a public-facing web service — see [Roadmap](#roadmap).

## Roadmap

- [x] Replace Ollama with Groq API (Llama 3.3 70B) for cloud inference
- [x] Expose `/chat` POST endpoint via FastAPI
- [x] Add IP-based rate limiting (`slowapi`)
- [ ] Deploy backend to Hugging Face Spaces (Docker SDK)
- [ ] Build vanilla JS chat widget for portfolio site integration
- [ ] Embed widget into [emirhanyildirim.me](https://emirhanyildirim.me) (Jekyll / GitHub Pages)

## Demo

![Actual terminal interface](static/interface.png)
_Real terminal output: retrieved chunks with similarity scores, project filtering, and grounded answer generation._

## Architecture

```
documents/               ← prepared knowledge base
    ├── *_README.md      ← project README files
    ├── *_code_context.txt  ← AST-extracted code structure
    └── *_highlights.txt ← curated project summaries & rationale

prepare_docs.py          ← knowledge base builder
rag_chatbot.py           ← retrieval + generation pipeline
chroma_db/               ← persistent vector index
```

**Pipeline:**

1. `prepare_docs.py` extracts structured context from each project
2. Chunks are embedded with `all-MiniLM-L6-v2` and stored in ChromaDB
3. At query time: project keyword detection → metadata-filtered retrieval → Groq generation with strict grounding prompt

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

**Cloud inference dependency:** Generation requires a valid `GROQ_API_KEY`. If the Groq API is unreachable, the endpoint returns an error string rather than a structured fallback.

## Setup

```bash
pip install -r requirements.txt

# Set up API key
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

# Build knowledge base
python prepare_docs.py

# Start CLI chatbot
python rag_chatbot.py

# Or start FastAPI server
fastapi dev app.py
```

**LLM:** Groq API with `llama-3.3-70b-versatile`. Requires `GROQ_API_KEY` in `.env`.

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
