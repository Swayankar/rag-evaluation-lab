# RAG Evaluation Lab

An experimental retrieval-augmented generation (RAG) system for asking questions over a collection of PDF documents and comparing how chunking and retrieval choices affect answer quality. The repository currently contains the Python backend, command-line workflows, and experiment/evaluation tooling.

> **Frontend: work in progress.** The `frontend/` directory is not completed yet. For now, use the API or the backend command-line scripts.

## What it does

- Loads PDFs from department folders, extracts and cleans their text, and attaches document, department, year, and page metadata.
- Splits documents with fixed-size or semantic chunking.
- Retrieves context using vector similarity, BM25 keyword search, hybrid vector + BM25 search, or hybrid search with cross-encoder reranking.
- Generates answers grounded in retrieved passages and returns citations and retrieved chunks.
- Evaluates retrieval, citations, answer quality, faithfulness, and system metrics locally; optionally sends traces and experiments to LangSmith.
- Runs configured strategy comparisons and saves JSON reports for inspection and the API.

## Project layout

```text
backend/
  app/                 FastAPI app and RAG, ingestion, retrieval, evaluation modules
  data/documents/      Example PDF corpus grouped by department
  scripts/             Ingestion, vector-store, query, and evaluation commands
  tests/               Pytest suite
experiments/           Five checked-in experiment configurations and result directory
frontend/              Frontend work in progress
main.py                Project scaffold entry point (not the API server)
pyproject.toml         Python project metadata and dependencies
```

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/) for dependency and environment management
- A Groq API key for answer generation and LLM-judged evaluation
- Internet access the first time sentence-transformer or reranker models are used, so their model files can be downloaded

The default embedding backend is `sentence_transformers` with `all-MiniLM-L6-v2`. If the model is unavailable, the code can fall back to a hashing embedder; this is useful for checking that the pipeline runs, but its retrieval results are not a meaningful quality baseline. Cross-encoder reranking can also fall back to a no-op reranker when its model cannot load.

## Setup

From the repository root:

```bash
uv sync
```

Create a `.env` file in the repository root and set at least:

```dotenv
GROQ_API_KEY=your_groq_api_key
```

Optional settings (defaults are defined in `backend/app/core/config.py`):

| Variable | Default | Purpose |
| --- | --- | --- |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Model used for answer generation and LLM judge calls |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` | Groq-compatible API base URL |
| `EMBEDDING_BACKEND` | `sentence_transformers` | `sentence_transformers` or `hashing` |
| `EMBEDDING_MODEL_NAME` | `all-MiniLM-L6-v2` | Sentence-transformer model name |
| `FIXED_CHUNK_SIZE` | `500` | Fixed chunk size in tokens |
| `FIXED_CHUNK_OVERLAP` | `50` | Overlap between fixed chunks in tokens |
| `LANGCHAIN_TRACING_V2` | `false` | Enable optional LangSmith tracing when credentials are configured |
| `LANGCHAIN_API_KEY` | empty | LangSmith API key |
| `LANGCHAIN_PROJECT` | `rag-evaluation-lab` | LangSmith project name |
| `LANGSMITH_ENDPOINT` | empty | Optional LangSmith endpoint override |

Configuration is loaded from the root `.env` file. Keep API keys private; `.env` is git-ignored.

## Quick start: ingest and ask

The repository includes sample PDFs under `backend/data/documents/`. Add your own PDFs to `backend/data/documents/<department>/`; the department folder name is used as document metadata.

Run backend scripts from the `backend/` directory. After `uv sync` at the root, activate the project environment first (`.venv\\Scripts\\Activate.ps1` in PowerShell, or `source .venv/bin/activate` on macOS/Linux):

```bash
cd backend
python scripts/ingest_documents.py --chunking fixed
python scripts/build_vector_store.py --chunking fixed
python scripts/ask_question.py "How many weeks of parental leave do employees get?"
```

Semantic chunking has its own chunk file and vector store. Build both before querying with that chunking option:

```bash
python scripts/ingest_documents.py --chunking semantic
python scripts/build_vector_store.py --chunking semantic
python scripts/ask_question.py "What is the parental leave policy?" --chunking semantic --strategy hybrid
```

`ingest_documents.py --chunking both` generates and summarizes both chunking variants. Re-run ingestion and vector-store building when the PDF corpus changes.

## Run the API

From `backend/` with the project environment active:

```bash
uvicorn app.main:app --reload
```

The API listens at `http://127.0.0.1:8000`. Interactive API documentation is at `/docs`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Health check |
| `POST` | `/query` | Ask a question; accepts optional `top_k` and retrieval strategy override |
| `GET` | `/documents` | List documents represented in the fixed chunks file |
| `GET` | `/experiments` | Read the latest saved experiment comparison |
| `GET` | `/experiments/{experiment_name}` | Read a saved experiment detail report |

Example request:

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"How do I request vacation?","top_k":5,"retrieval_strategy":"hybrid"}'
```

Supported retrieval strategy values are `vector`, `bm25`, `hybrid`, and `hybrid_rerank`. The selected strategy must have its required chunk/vector-store artifacts available. `/documents` needs fixed-chunk ingestion, and the experiment routes need comparison results generated first.

## Evaluation and experiment workflow

Create (or validate) the starter evaluation dataset, then edit `backend/data/evaluation/questions.json` so `relevant_document_ids` match PDF filenames without the extension:

```bash
cd backend
python scripts/create_eval_dataset.py
```

Build chunks and vector stores for the strategies you want to compare, then run all configs in `experiments/`:

```bash
python scripts/ingest_documents.py --chunking both
python scripts/build_vector_store.py --chunking fixed
python scripts/build_vector_store.py --chunking semantic
python scripts/compare_experiments.py
```

The five checked-in configurations cover fixed/vector, semantic/vector, fixed/hybrid, semantic/hybrid, and semantic/hybrid with reranking. Missing prerequisites are reported and those configurations are skipped. Reports are written under `experiments/results/`, including `comparison_latest.json` and per-strategy detail files.

To run one strategy instead:

```bash
python scripts/run_experiment.py --chunking fixed --strategy vector
```

Local evaluation includes Recall@K, Precision@K, MRR, citation metrics, latency, and approximate token counts. Answer correctness and faithfulness use Groq as an LLM judge; omit those calls with `--no-llm-judges`:

```bash
python scripts/run_experiment.py --chunking fixed --strategy vector --no-llm-judges
python scripts/compare_experiments.py --no-llm-judges
```

LangSmith experiments are optional. Configure `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY`; use `python scripts/run_experiment.py --langsmith` to publish an experiment run. Traces may contain questions, prompts, and retrieved document text, so enable tracing only when that data can be sent to the configured LangSmith project.

## Tests

Run the existing test suite from the repository root:

```bash
uv run pytest
```

## Generated files

Ingested chunks, vector stores, evaluation datasets/results, and experiment result JSON are generated locally and git-ignored. Raw PDFs and the checked-in experiment configuration JSON files are part of the repository.