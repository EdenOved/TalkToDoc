import json
from typer.testing import CliRunner
from app import app as cli_app
from idea_indexer.paths import ARTIFACTS_DIR, OUTPUTS_DIR
from idea_indexer.llm.llm_client import LLMClient

runner = CliRunner()


def test_full_pipeline_runs():
    # Reset pipeline
    r = runner.invoke(cli_app, ["reset"])
    assert r.exit_code == 0

    # Ingest documents
    r = runner.invoke(cli_app, ["ingest"])
    assert r.exit_code == 0
    assert (ARTIFACTS_DIR / "pages.jsonl").exists()

    # Build TF-IDF index
    r = runner.invoke(cli_app, ["build-index"])
    assert r.exit_code == 0
    assert (ARTIFACTS_DIR / "tfidf.pkl").exists()

    orig_chat = LLMClient.chat
    LLMClient.chat = lambda self, _: json.dumps({
        "project_id": "1",
        "project_title": "Project_Test"
    }, ensure_ascii=False)

    try:
        r = runner.invoke(cli_app, ["extract"])
        assert r.exit_code == 0
        assert (OUTPUTS_DIR / "manifest.jsonl").exists()
    finally:
        LLMClient.chat = orig_chat


def test_query_returns_json():
    r = runner.invoke(cli_app, ["reset"])
    assert r.exit_code == 0

    r = runner.invoke(cli_app, ["ingest"])
    assert r.exit_code == 0

    r = runner.invoke(cli_app, ["build-index"])
    assert r.exit_code == 0

    r = runner.invoke(cli_app, ["query", "--q", "project start date"])
    assert r.exit_code == 0
    obj = json.loads(r.stdout)
    assert "results" in obj
    assert isinstance(obj["results"], list)
