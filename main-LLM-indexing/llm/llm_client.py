import json
from pathlib import Path
from idea_indexer.utils.cache import SimpleCache
from idea_indexer.utils.costlog import CostLogger
from idea_indexer.settings import settings
from openai import OpenAI


# Thin LLM wrapper with cache and simple cost logging.
class LLMClient:
    def __init__(self, cache_dir: Path, cost_log_path: Path):
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache = SimpleCache(cache_dir)
        self.cost_logger = CostLogger(cost_log_path)
        self.client = None

    # Create OpenAI client once, if API key exists.
    def _ensure_client(self) -> bool:
        if self.client is not None:
            return True
        if not settings.openai_api_key or OpenAI is None:
            return False
        try:
            self.client = OpenAI(api_key=settings.openai_api_key)
            return True
        except Exception:
            self.client = None
            return False

    # Stable cache key
    def _cache_key(self, model: str, content: str) -> str:
        return json.dumps({"m": model, "c": content}, ensure_ascii=False)

    # Return raw LLM string response (or JSON error stub on failure)
    def chat(self, content: str) -> str:
        key = self._cache_key(settings.openai_model, content)
        cached = self.cache.get(key)
        if cached:
            return cached

        # Budget guard
        if self.cost_logger.total_cost() >= settings.token_budget_usd:
            stub = json.dumps({"error": "budget_exceeded",
                               "message": f"Token budget (${settings.token_budget_usd}) exceeded. Skipping call."},
                              ensure_ascii=False)
            self.cost_logger.log(settings.openai_model, 0,
                                 0, error="budget_exceeded")
            self.cache.set(key, stub)
            return stub

        if not self._ensure_client():
            stub = json.dumps({"error": "no_api_key_or_client",
                               "message": "Skipped LLM call due to missing API key or client."},
                              ensure_ascii=False)
            self.cost_logger.log(settings.openai_model, 0,
                                 0, error="no_api_key_or_client")
            self.cache.set(key, stub)
            return stub

        try:
            res = self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system",
                        "content": "You are an extraction service. Output only JSON."},
                    {"role": "user", "content": content},
                ],
            )
            out = (res.choices[0].message.content or "").strip()
            usage = getattr(res, "usage", None)
            pt = getattr(usage, "prompt_tokens", 0) or 0
            ct = getattr(usage, "completion_tokens", 0) or 0
            self.cost_logger.log(settings.openai_model, pt, ct, error=None)
        except Exception as e:
            out = json.dumps({"error": str(e)}, ensure_ascii=False)
            self.cost_logger.log(settings.openai_model, 0, 0, error=str(e))

        self.cache.set(key, out)
        return out
