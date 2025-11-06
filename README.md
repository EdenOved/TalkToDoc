# TalkToDoc
**By:** Eden Oved

## Introduction
TalkToDoc is a local AI-powered system that lets you *"talk with your documents"* - just like ChatGPT, but **fully local and private**.

It ingests PDF and Excel files, stores the text in a **PostgreSQL database**, builds a **searchable TF-IDF index**, and extracts structured project data into clean JSON files - including project timelines, milestones, contacts, keywords, and summaries.

The system minimizes LLM usage (under $3 total), caches all calls locally, and outputs both extracted answers and references to the source documents.

---

## Pipeline Overview
1. **Ingest** all documents under `data/` → stored in PostgreSQL + `artifacts/pages.jsonl`
2. **Build Index** using TF-IDF → `artifacts/tfidf.pkl` + DB `page_vectors`
3. **Group documents** by project ID
4. **Pre-filter** relevant pages per query
5. **Extract** structured fields using OpenAI (`LLMClient`)
6. **Cache & track token cost** → `outputs/cost_log.jsonl`
7. **Output** per-project structured summaries

---

## Tools & Libraries
- **Python 3.11**
- **PostgreSQL (via Docker)**
- **Typer (CLI)**
- **pandas**
- **PyMuPDF**
- **scikit-learn**
- **psycopg2**
- **openai**
- **Docker + docker-compose**

---

## Setup

1. Copy `.env.example` → `.env` and set:
```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
TOKEN_BUDGET_DOLLARS=3.0
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=talk_to_doc
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

2. Place your project folders and files under:
```
./data/
```

---

## Run the System

```bash
docker compose up -d --build
docker compose exec app python app.py ingest
docker compose exec app python app.py build-index
docker compose exec app python app.py extract
```

### Query Example:
You can ask questions in natural language, and the system will return **relevant pages + evidence** from your documents:

```bash
docker compose exec app python app.py query --q "project start date"
```

---

## Reset (Clean Re-Run)
Removes all files under `artifacts/` and `outputs/` for a clean rerun.

```bash
docker compose exec app python app.py reset
```

---

## Tests (optional)
Run automated pipeline tests (reset → ingest → index → extract → query).  

```bash
docker compose exec app pytest -q
```

---

## Output Files

| File / Folder                   | Description                              |
| ------------------------------- | ---------------------------------------- |
| `artifacts/pages.jsonl`         | Extracted text chunks                    |
| `artifacts/tfidf.pkl`           | TF-IDF index + vectorizer                |
| `artifacts/cache/`              | Local cache of LLM responses             |
| `outputs/index.jsonl`           | Search index (debug/inspection)          |
| `outputs/manifest.jsonl`        | Summary of ingested documents            |
| `outputs/PRJ-*_key_params.json` | LLM extraction project metadata          |
| `outputs/cost_log.jsonl`        | Token usage + LLM cost log               |

---

**Built by [Eden Oved](https://github.com/edenoved)**  
AI-driven document indexing and extraction project.
