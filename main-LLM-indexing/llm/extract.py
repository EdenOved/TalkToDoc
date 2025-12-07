from pathlib import Path
import json
from typing import List, Dict
from idea_indexer.paths import ARTIFACTS_DIR, OUTPUTS_DIR
from idea_indexer.utils.jsonl import read_jsonl
import joblib
from sklearn.metrics.pairwise import cosine_similarity
from idea_indexer.llm.llm_client import LLMClient

SCHEMA_EXAMPLE = {
    "project_id": "",
    "project_title": "",
    "start_date": "",
    "end_date": "",
    "key_dates": [],
    "contacts": [],
    "work_summary": "",
    "top_keywords": [],
    "evidence": [],
}

# Minimal prompt that asks the LLM to return JSON matching the schema.
PROMPT_TEMPLATE = (
    "System: You are an extraction service. Output only JSON matching the schema.\n"
    "User: Given these document excerpts, extract fields and return JSON exactly matching the schema.\n"
    "Schema: {schema}\n"
    "Excerpts:\n{excerpts}\n"
)


# Rank top-k relevant docs using TF-IDF cosine similarity.
def rank_topk(tfidf_pkl: Path, pages_jsonl: Path, query: str, k: int = 12) -> List[Dict]:

    vectorizer, X = joblib.load(tfidf_pkl)
    docs = list(read_jsonl(pages_jsonl))
    qvec = vectorizer.transform([query])
    sims = cosine_similarity(qvec, X)[0]
    top = sorted([(i, float(sims[i])) for i in range(len(sims))],
                 key=lambda x: x[1], reverse=True)[:k]

    hits = []
    for idx, score in top:
        d = docs[idx]
        rec = {
            "score": score,
            "file_path": d["file_path"],
            "project_id": d["project_id"],
            "text": d.get("text", "")[:1200],
        }
        if "page" in d:
            rec["page"] = d["page"]
        if "sheet" in d:
            rec["sheet"] = d["sheet"]
        if "row" in d:
            rec["row"] = d["row"]
        hits.append(rec)
    return hits


# Collect project evidence, call the LLM, and fill schema keys (use LLM values or empty defaults).
def extract_for_project(project_id: str, tfidf_pkl: Path, pages_jsonl: Path) -> Dict:
    queries = [
        "start date end date milestones schedule",
        "contacts email phone",
        "project summary scope overview",
        "top keywords topics",
        "תאריך התחלה תאריך סיום לוח זמנים אבני דרך",
        "אנשי קשר אימייל טלפון",
    ]

    evidence = []
    seen = set()
    for q in queries:
        hits = [h for h in rank_topk(tfidf_pkl, pages_jsonl, q, k=12)
                if h.get("project_id") == project_id]
        for h in hits:
            key = (h["file_path"], h.get("page", 0),
                   h.get("sheet"), h.get("row"))
            if key in seen:
                continue
            seen.add(key)
            evidence.append(h)
            if len(evidence) >= 8:
                break
        if len(evidence) >= 8:
            break

    if not evidence:
        docs = [d for d in read_jsonl(pages_jsonl) if d.get(
            "project_id") == project_id]
        seen = set()
        for d in docs:
            key = (d["file_path"], d.get("page", 0),
                   d.get("sheet"), d.get("row"))
            if key in seen:
                continue
            seen.add(key)
            evidence.append({
                "score": 0.0,
                "file_path": d["file_path"],
                "page": int(d.get("page", 0)),
                "project_id": project_id,
                "text": (d.get("text") or "")[:1200],
            })
            if len(evidence) >= 5:
                break

    excerpts = []
    for h in evidence[:10]:
        snippet = h.get("text", "")
        page_s = f"page {h.get('page', 0)}" if "page" in h else ""
        loc = page_s or (
            f"sheet {h.get('sheet')} row {h.get('row')}" if "sheet" in h or "row" in h else "")
        excerpts.append(
            f"[{h['file_path']} | {loc} | score {h.get('score',0):.3f}]\n{snippet}")

    schema = json.dumps(SCHEMA_EXAMPLE, ensure_ascii=False)
    content = PROMPT_TEMPLATE.format(
        schema=schema, excerpts="\n\n".join(excerpts))

    llm = LLMClient(ARTIFACTS_DIR / "cache", OUTPUTS_DIR / "cost_log.jsonl")

    raw = {}
    try:
        out = llm.chat(content)
        if out and out.strip().startswith("{"):
            raw = json.loads(out)
    except Exception:
        raw = {}

    data = {}
    for key, value in SCHEMA_EXAMPLE.items():
        if isinstance(value, list):
            data[key] = list(value)
        else:
            data[key] = value

    for key, value in (raw or {}).items():
        if key in data:
            data[key] = value

    data["project_id"] = project_id
    data["evidence"] = [
        {
            "doc_path": h.get("file_path", ""),
            "page": h.get("page", 0),
            "snippet": (h.get("text") or h.get("value") or "")[:400],
        }
        for h in evidence
    ]

    return data
