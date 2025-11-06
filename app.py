import typer
import json
import shutil
import joblib
import psycopg2
import os
import numpy as np
from idea_indexer.paths import DATA_DIR, ARTIFACTS_DIR, OUTPUTS_DIR
from idea_indexer.utils.jsonl import write_jsonl, read_jsonl
from idea_indexer.utils.pdf_text import extract_pdf_pages
from idea_indexer.utils.excel_extractor import extract_excel
from idea_indexer.indexing.index_builder import build_index
from idea_indexer.llm.extract import extract_for_project
from idea_indexer.utils.jsonl import write_json
from sklearn.metrics.pairwise import cosine_similarity
from shutil import copyfile


app = typer.Typer(help="Mini Knowledge Indexer (OpenAI)")


def get_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "db"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        dbname=os.getenv("POSTGRES_DB", "idea_indexer")
    )

# Parse data/ and write artifacts/pages.jsonl


@app.command()
def ingest():
    rows = []
    for i, proj_dir in enumerate(sorted(DATA_DIR.iterdir()), start=1):
        if not proj_dir.is_dir():
            continue
        project_title = proj_dir.name
        project_id = f"PRJ-{project_title}"

        for f in sorted(proj_dir.iterdir()):
            try:
                if f.suffix.lower() == ".pdf":
                    for page, text in extract_pdf_pages(f):
                        if text.strip():
                            rows.append({
                                "file_path": str(f),
                                "page": page,
                                "text": text,
                                "project_id": project_id,
                                "project_title": project_title,
                            })
                elif f.suffix.lower() in {".xls", ".xlsx"}:
                    for rec in extract_excel(f):
                        rec.update({"project_id": project_id,
                                   "project_title": project_title})
                        rows.append(rec)
            except Exception:
                continue

    out_path = ARTIFACTS_DIR / "pages.jsonl"
    write_jsonl(out_path, rows)

   # --- Save ingested pages into DB ---
    conn = get_conn()
    page_ids = []
    with conn:
        with conn.cursor() as cur:
            for r in rows:
                cur.execute("""
                    INSERT INTO pages (project_id, project_title, file_path, page, text)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (project_id, file_path, page) DO NOTHING
                    RETURNING id
                """, (
                    r.get("project_id"),
                    r.get("project_title", ""),
                    str(r.get("file_path")),
                    int(r.get("page", 0)),
                    r.get("text", "")
                ))
                row = cur.fetchone()
                if row is not None:
                    page_ids.append(row[0])
                else:
                    # אם כבר קיים – נביא את ה-id הקיים כדי לשמור על סנכרון page_ids.jsonl
                    cur.execute("""
                        SELECT id FROM pages
                        WHERE project_id=%s AND file_path=%s AND page=%s
                    """, (r.get("project_id"), str(r.get("file_path")), int(r.get("page", 0))))
                    page_ids.append(cur.fetchone()[0])

    conn.close()

    write_jsonl(ARTIFACTS_DIR / "page_ids.jsonl", page_ids)
    print(f"✅ Saved {len(rows)} pages to database")

    typer.echo(f"Ingested {len(rows)} items -> {out_path}")

# Build TF-IDF and write outputs/index.jsonl


@app.command("build-index")
def build_index_cmd():
    pages = ARTIFACTS_DIR / "pages.jsonl"
    tfidf_pkl = ARTIFACTS_DIR / "tfidf.pkl"
    build_index(pages, tfidf_pkl)
    typer.echo(f"Built TF-IDF index -> {tfidf_pkl}")

    copyfile(pages, OUTPUTS_DIR / "index.jsonl")
    typer.echo(f"Wrote {OUTPUTS_DIR / 'index.jsonl'}")

    # --- Persist TF-IDF vectors into DB aligned with page_ids ---
    vectorizer, X = joblib.load(ARTIFACTS_DIR / "tfidf.pkl")
    page_ids = list(read_jsonl(ARTIFACTS_DIR / "page_ids.jsonl"))

    if X.shape[0] != len(page_ids):
        raise RuntimeError(
            f"Vector rows ({X.shape[0]}) != page_ids count ({len(page_ids)})")

    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            for i, pid in enumerate(page_ids):
                vec_list = X[i].toarray()[0].tolist()
                cur.execute("""
                    INSERT INTO page_vectors (page_id, vector)
                    VALUES (%s, %s)
                    ON CONFLICT (page_id) DO UPDATE SET vector = EXCLUDED.vector
                """, (int(pid), vec_list))
    conn.close()
    typer.echo(f"Stored {len(page_ids)} vectors into database")


# Run LLM extraction per project + write manifest.jsonl


@app.command()
def extract():
    pages = ARTIFACTS_DIR / "pages.jsonl"
    tfidf_pkl = ARTIFACTS_DIR / "tfidf.pkl"

    proj_map = {}
    for r in read_jsonl(pages):
        pid = r.get("project_id")
        ptitle = r.get("project_title") or ""
        if pid and pid not in proj_map:
            proj_map[pid] = ptitle

    for pid, ptitle in proj_map.items():
        data = extract_for_project(pid, tfidf_pkl, pages)
        if not data.get("project_title"):
            data["project_title"] = ptitle or ""

        out_path = OUTPUTS_DIR / f"{pid}_key_params.json"
        write_json(out_path, data)
        typer.echo(f"Wrote {out_path}")

        # --- Persist extracted project data into DB ---
        conn = get_conn()
        with conn:
            with conn.cursor() as cur:
                # Project info
                cur.execute("""
                    INSERT INTO projects (project_id, project_title, start_date, end_date, work_summary)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (project_id) DO UPDATE SET
                    project_title = EXCLUDED.project_title,
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date,
                    work_summary = EXCLUDED.work_summary
                """, (
                    pid,
                    data.get("project_title") or ptitle or "",
                    data.get("start_date"),
                    data.get("end_date"),
                    data.get("work_summary") or data.get("summary") or ""
                ))

                # Key dates
                for kd in (data.get("key_dates") or []):
                    cur.execute("""
                        INSERT INTO key_dates (project_id, label, date_val, source_file, page)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (pid, kd.get("label"), kd.get("date"),
                          kd.get("source_file"),
                          str(kd.get("page")) if kd.get("page") is not None else None))

                # Contacts
                for c in (data.get("contacts") or []):
                    cur.execute("""
                        INSERT INTO contacts (project_id, name, role, email_addr, phone)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (pid, c.get("name"), c.get("role"), c.get("email"), c.get("phone")))

                # Keywords
                kws = data.get("top_keywords") or data.get("keywords") or []
                for kw in kws:
                    if isinstance(kw, dict):
                        word = kw.get("keyword") or kw.get(
                            "word") or kw.get("text")
                        weight = kw.get("weight")
                    else:
                        word, weight = str(kw), None
                    cur.execute("""
                        INSERT INTO keywords (project_id, keyword, weight)
                        VALUES (%s, %s, %s)
                    """, (pid, word, weight))

                # Evidence
                for ev in (data.get("evidence") or []):
                    cur.execute("""
                        INSERT INTO evidence (project_id, file_path, page, snippet, score)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (pid,
                          ev.get("file_path"),
                          str(ev.get("page")) if ev.get(
                              "page") is not None else None,
                          ev.get("snippet"),
                          ev.get("score")))
        conn.close()

    rows = list(read_jsonl(pages))
    seen = set()
    manifest = []
    for r in rows:

        doc = r.get("file_path_rel") or r.get("file_path")
        if not doc or doc in seen:
            continue
        seen.add(doc)
        manifest.append({
            "doc_path": doc,
            "project_id": r.get("project_id", ""),
            "project_title": r.get("project_title", ""),
        })
    write_jsonl(OUTPUTS_DIR / "manifest.jsonl", manifest)
    typer.echo(f"Wrote {OUTPUTS_DIR / 'manifest.jsonl'}")

# Local search over TF-IDF (no LLM calls)


@app.command()
def query(q: str = typer.Option(..., "--q", help="Your question")):

    # נטען רק את הווקטורייזר מה-pkl (X נבנה מה-DB)
    vectorizer, _ = joblib.load(ARTIFACTS_DIR / "tfidf.pkl")

    # נטען את הדוקומנטים לפי ה-ingest האחרון (pages.jsonl)
    docs = list(read_jsonl(ARTIFACTS_DIR / "pages.jsonl"))

    # נטען את page_ids.jsonl כדי לשמור יישור מדויק בין docs לבין הווקטורים
    page_ids_path = ARTIFACTS_DIR / "page_ids.jsonl"
    page_ids = [int(x) for x in read_jsonl(page_ids_path)
                ] if page_ids_path.exists() else []

    # נקרא מה-DB את הווקטורים רק עבור ה-ids האלו
    conn = get_conn()
    with conn.cursor() as cur:
        # נביא (page_id, vector) למילון
        cur.execute(
            "SELECT page_id, vector FROM page_vectors WHERE page_id = ANY(%s)", (page_ids,))
        rows = cur.fetchall()
    conn.close()

    vec_by_id = {pid: np.array(vec) for (pid, vec) in rows}

    X_list = [vec_by_id[pid] for pid in page_ids if pid in vec_by_id]
    X = np.vstack(X_list) if X_list else np.empty((0, 0))

    # אם אין בכלל וקטורים – נחזיר תוצאה ריקה במקום להתרסק
    if X.size == 0 or X.shape[0] == 0:
        typer.echo(json.dumps({"query": q, "results": []},
                              ensure_ascii=False, indent=2))
        return

    # אם מסיבה כלשהי האורך לא זהה, נגביל את docs לאותו אורך כדי לא לקבל IndexError
    if len(docs) != len(X_list):
        docs = docs[:len(X_list)]

    qvec = vectorizer.transform([q])
    sims = cosine_similarity(qvec, X)[0]
    idxs = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)[:5]

    out = []
    for i in idxs:
        d = docs[i]
        loc = {}
        if "page" in d:  # PDF
            loc["page"] = d["page"]
        else:            # Excel
            if "sheet" in d:
                loc["sheet"] = d["sheet"]
            if "row" in d:
                loc["row"] = d["row"]

        out.append({
            "file_path": d["file_path"],
            **loc,
            "score": float(sims[i]),
            "snippet": d["text"][:400]
        })

    typer.echo(json.dumps({"query": q, "results": out},
               ensure_ascii=False, indent=2))


# Developer utility - clears artifacts / and outputs / (not part of main flow)
@app.command()
def reset():
    for p in [ARTIFACTS_DIR, OUTPUTS_DIR]:
        if p.exists():
            for child in p.iterdir():
                if child.is_file():
                    child.unlink()
                else:
                    shutil.rmtree(child, ignore_errors=True)
    typer.echo("Cleared artifacts/ and outputs/.")


if __name__ == "__main__":
    app()
