# RAG Evaluation Lab

RAG Evaluation Lab is a local application for exploring retrieval-augmented generation (RAG) over PDF collections. It includes a FastAPI backend, a React/Vite web interface, command-line ingestion and evaluation tools, and configurable experiment workflows. You can ask questions with citations, inspect retrieved passages, manage a document library, and compare chunking and retrieval strategies using a repeatable evaluation dataset.

## Features

- Ingest PDF files grouped in department folders, extract page text, clean it, and attach document, department, year, and page metadata.
- Create fixed-size or embedding-based semantic chunks and build a vector index for each chunking mode.
- Retrieve with vector similarity, BM25 keyword search, hybrid vector/BM25 search, or hybrid search followed by cross-encoder reranking.
- Generate answers from retrieved context with source citations through the Groq chat completions API.
- Run a single query or compare up to all eight chunking/retrieval combinations side by side.
- Evaluate retrieval quality, citations, answer quality, faithfulness, latency, and approximate token use; run locally or optionally publish traces and experiments to LangSmith.
- Manage PDFs and department folders in the UI or API, check index freshness, rebuild indexes, and reset the library.
- Save and compare named experiment configurations, with aggregate and per-question reports.

## Repository map

```text
.
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI routes for query, documents, evaluation, experiments, jobs, config
│   │   ├── core/            # Settings, dependencies, logging, in-memory background jobs
│   │   ├── ingestion/       # PDF loading, cleaning, metadata, chunk/index building
│   │   ├── chunking/        # Fixed-size and semantic chunkers
│   │   ├── embeddings/      # Sentence-transformer and fallback embedding support
│   │   ├── retrieval/       # Vector, BM25, hybrid retrieval and reranking
│   │   ├── generation/      # Groq client, prompts, answer generation
│   │   ├── pipelines/       # Strategy selection and end-to-end RAG pipeline
│   │   ├── evaluation/      # Dataset, runner, metrics and evaluators
│   │   ├── experiments/     # Config registry, batch runner, comparison and recommendations
│   │   ├── tracing/         # Optional LangSmith tracing integration
│   │   └── models/          # Internal and API data models
│   ├── data/
│   │   ├── documents/       # Example PDF corpus organized by department
│   │   ├── evaluation/      # Evaluation question set and generated results
│   │   └── processed/       # Generated chunks and vector indexes
│   ├── scripts/             # Ingestion, indexing, query, evaluation and experiment commands
│   └── tests/               # Pytest coverage for backend modules and APIs
├── experiments/             # Checked-in experiment_*.json configurations and generated reports
├── frontend/
│   └── src/                 # React pages, components, charts, API client and helpers
├── main.py                  # Small Python scaffold entry point; does not start the API
├── pyproject.toml / uv.lock # Python dependencies and lockfile
└── README.md
```

## Requirements

- Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).
- Node.js and npm to run the web interface.
- A Groq API key for answer generation and optional LLM-judged evaluation.
- Network access on first use if sentence-transformer or cross-encoder model files need downloading.

The default embedding configuration uses `sentence-transformers` with `all-MiniLM-L6-v2`. If that model cannot be loaded, the application can use a hashing fallback so the pipeline can still run; hashing embeddings are not a meaningful semantic retrieval baseline. If the cross-encoder cannot load, reranking falls back to a no-op and `hybrid_rerank` effectively behaves like hybrid retrieval. Token counts use `tiktoken` when available and otherwise are approximate.

## Configuration

Install the Python environment from the repository root:

```bash
uv sync
```

Create a root `.env` file. At minimum, configure Groq for answering questions:

```dotenv
GROQ_API_KEY=your_groq_api_key
```

Settings are loaded by `backend/app/core/config.py` from this root `.env` file. Defaults:

| Variable                         | Default                          | Purpose                                                            |
| -------------------------------- | -------------------------------- | ------------------------------------------------------------------ |
| `GROQ_API_KEY`                   | empty                            | Groq API credential; required for generated answers and LLM judges |
| `GROQ_MODEL`                     | `openai/gpt-oss-20b`             | Model used for generation and LLM judge calls                      |
| `GROQ_BASE_URL`                  | `https://api.groq.com/openai/v1` | OpenAI-compatible Groq API base URL                                |
| `EMBEDDING_BACKEND`              | `sentence_transformers`          | `sentence_transformers` or `hashing`                               |
| `EMBEDDING_MODEL_NAME`           | `all-MiniLM-L6-v2`               | Sentence-transformer embedding model                               |
| `FIXED_CHUNK_SIZE`               | `500`                            | Fixed chunk length in tokens                                       |
| `FIXED_CHUNK_OVERLAP`            | `50`                             | Token overlap between fixed chunks                                 |
| `SEMANTIC_BREAKPOINT_PERCENTILE` | `90.0`                           | Semantic distance percentile used to detect topic boundaries       |
| `SEMANTIC_MIN_CHUNK_TOKENS`      | `150`                            | Minimum semantic chunk size                                        |
| `SEMANTIC_MAX_CHUNK_TOKENS`      | `700`                            | Maximum semantic chunk size                                        |
| `LANGCHAIN_TRACING_V2`           | `false`                          | Enables LangSmith tracing when an API key is also configured       |
| `LANGCHAIN_API_KEY`              | empty                            | LangSmith API credential                                           |
| `LANGCHAIN_PROJECT`              | `rag-evaluation-lab`             | LangSmith project name                                             |
| `LANGSMITH_ENDPOINT`             | empty                            | Optional LangSmith endpoint override                               |

Keep credentials private; `.env` is git-ignored. Traces can include questions, prompts, and retrieved document text.

## Quick start: build an index and ask a question

Sample PDFs are included under `backend/data/documents/`. Add PDFs to `backend/data/documents/<department>/`; the folder name becomes the department metadata. From the repository root, activate the uv environment and run the backend scripts from `backend/`:

```powershell
.venv\Scripts\Activate.ps1
cd backend
python scripts/ingest_documents.py --chunking fixed
python scripts/build_vector_store.py --chunking fixed
python scripts/ask_question.py "How many weeks of parental leave do employees get?"
```

For semantic chunking, build its chunks and vector store before querying it:

```powershell
python scripts/ingest_documents.py --chunking semantic
python scripts/build_vector_store.py --chunking semantic
python scripts/ask_question.py "What is the parental leave policy?" --chunking semantic --strategy hybrid
```

`ingest_documents.py --chunking both` creates both chunk files and prints a summary for comparison. Re-run ingestion and index building whenever the source PDFs or chunking settings change. Files are stored relative to `backend/`: chunks in `data/processed/chunks/`, and vector indexes in `data/processed/vector_store/` (fixed) and `data/processed/vector_store_semantic/` (semantic).

Available retrieval strategies are `vector`, `bm25`, `hybrid`, and `hybrid_rerank`. The query command accepts `--chunking`, `--strategy`, and `--top-k` (default 5).

## Run the API and web app

Start the backend from `backend/`:

```bash
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive OpenAPI documentation is at `http://127.0.0.1:8000/docs`.

Start the frontend in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Vite serves the UI at `http://localhost:5173`. The frontend uses `http://localhost:8000` by default. To use another backend URL, set `VITE_API_URL` in the frontend environment before starting/building Vite. The backend currently enables permissive CORS for local development.

### Web app pages

- **Home** shows application status and configuration, explains the RAG workflow, and links into the lab.
- **Playground** asks questions, selects chunking and retrieval strategies, compares strategies, and displays generated answers, citations, and retrieved passages.
- **Documents** lists department folders and PDFs, accepts PDF uploads, creates/deletes empty folders, reports whether the fixed index is stale, starts index rebuilds, and offers a type-to-confirm reset workflow with options for evaluation and experiment data.
- **Evaluation** edits and saves the question set, runs evaluations as background jobs, and inspects, charts, and deletes saved result reports.
- **Experiments** edits experiment configurations, runs the configured strategies, compares aggregate scores, displays recommendations, and opens per-question results.

Long-running evaluation, experiment, and rebuild operations run in background threads. Their status and progress are exposed through the jobs API and retained in memory only (up to 20 recent jobs); restarting the backend clears job history.

## API overview

All routes are served by `backend/app/main.py`. The main endpoints are:

| Method          | Path                                 | Purpose                                                                                       |
| --------------- | ------------------------------------ | --------------------------------------------------------------------------------------------- |
| `GET`           | `/health`                            | Health check                                                                                  |
| `GET`           | `/config`                            | Active configuration, loaded pipeline types, and warnings                                     |
| `POST`          | `/query`                             | Answer a question; optional `top_k`, `chunking_strategy`, `retrieval_strategy`                |
| `POST`          | `/query/compare`                     | Run a question across requested strategies, or all eight combinations                         |
| `GET`           | `/documents`                         | List documents represented by the fixed chunks file                                           |
| `GET`           | `/documents/library`                 | Show on-disk library, index freshness, and chunk counts                                       |
| `POST`          | `/documents/folders`                 | Create a department folder                                                                    |
| `DELETE`        | `/documents/folders/{name}`          | Delete an empty department folder                                                             |
| `POST`          | `/documents/upload`                  | Upload one or more PDFs using multipart form fields `department` and `files` (25 MB per file) |
| `DELETE`        | `/documents/{department}/{filename}` | Delete a PDF from the library                                                                 |
| `POST`          | `/documents/rebuild`                 | Start a fixed/semantic index rebuild; poll its job                                            |
| `POST`          | `/documents/reset`                   | Delete the document library and index; optional clearing of evaluation/experiment data        |
| `GET`, `PUT`    | `/evaluation/questions`              | Read or replace the evaluation question set                                                   |
| `POST`          | `/evaluation/questions/starter`      | Create the starter evaluation dataset                                                         |
| `POST`          | `/evaluation/run`                    | Start an evaluation job                                                                       |
| `GET`           | `/evaluation/results`                | List saved evaluation reports                                                                 |
| `GET`, `DELETE` | `/evaluation/results/{name}`         | Read or delete one evaluation report                                                          |
| `GET`           | `/experiments`                       | Read the latest comparison report                                                             |
| `GET`           | `/experiments/overview`              | Summaries, rankings, and recommendations for experiment results                               |
| `GET`, `PUT`    | `/experiments/configs`               | Read or replace experiment definitions                                                        |
| `POST`          | `/experiments/run`                   | Start a configured experiment batch                                                           |
| `GET`           | `/experiments/{experiment_name}`     | Read one experiment detail report                                                             |
| `GET`           | `/jobs`, `/jobs/{job_id}`            | List or inspect background jobs; optionally filter by `kind`                                  |

Example query:

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"How do I request vacation?","top_k":5,"chunking_strategy":"fixed","retrieval_strategy":"hybrid"}'
```

API query requests default to fixed chunking and vector retrieval. Query responses include the answer, citations, retrieved chunks and scores, strategy names, and latency. A selected strategy needs its corresponding chunk and (for vector/hybrid retrieval) vector-store artifacts.

## Evaluation workflow

Create the starter evaluation dataset if it does not exist:

```bash
cd backend
python scripts/create_eval_dataset.py
```

The dataset is `backend/data/evaluation/questions.json`. Each question has an `id`, question text, `relevant_document_ids`, optional `expected_answer`, optional `expected_keywords`, and optional category. Document IDs are PDF filenames without the extension and are deliberately document-level so they remain valid across chunking changes. Keep IDs aligned with files in `data/documents/`.

Build the needed indexes, then run an evaluation:

```bash
python scripts/ingest_documents.py --chunking both
python scripts/build_vector_store.py --chunking fixed
python scripts/build_vector_store.py --chunking semantic
python scripts/run_experiment.py --chunking fixed --strategy vector
```

Local evaluation measures Recall@K, Precision@K, MRR, citation accuracy, latency, and approximate prompt/completion token counts. With LLM judges enabled (default), it also scores answer correctness, relevance, completeness, faithfulness, and likely hallucination using Groq. Skip judge calls with `--no-llm-judges`; deterministic retrieval/citation/system metrics still run. Reports are saved in `backend/data/evaluation/results/`.

## Experiment workflow

The root `experiments/experiment_*.json` files define strategy name, chunking strategy, retrieval strategy, and `top_k`. The included configurations explore fixed/vector, semantic/vector, fixed/hybrid, semantic/hybrid, and semantic/hybrid-rerank. Edit these files or use the UI/API to define a different set. Build the required chunking artifacts and run:

```bash
cd backend
python scripts/compare_experiments.py
```

Configurations with missing prerequisites are skipped and reported. Comparison output and per-strategy details are written to `experiments/results/`, including `comparison_latest.json`. Use `--no-llm-judges` to reduce Groq calls. For a single strategy use `scripts/run_experiment.py` with its `--chunking` and `--strategy` options.

LangSmith is optional. Set `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` to enable tracing. Run one experiment with `python scripts/run_experiment.py --langsmith`; `--trace-evaluators` also traces evaluator calls. Traces can contain private prompts and document text, so configure this only when you intend to send that data to LangSmith.

## Tests and frontend build

Run the backend test suite from the repository root:

```bash
uv run pytest
```

Build the frontend production bundle:

```bash
cd frontend
npm run build
```

## Generated and persistent data

Ingestion and index files, evaluation questions/results, and experiment result JSON are stored under the paths described above. Generated chunks, vector stores, and result files are local artifacts and git-ignored; source PDFs and experiment configuration JSON files are checked into the repository. Background job state is in memory and is lost when the API process restarts.
