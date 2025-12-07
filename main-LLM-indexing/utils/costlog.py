import json
from pathlib import Path
from datetime import datetime

PRICES = {"gpt-4o-mini": (0.00015, 0.0006), "gpt-4o": (0.005, 0.015)}


# Log LLM token usage and total cost to a JSONL file.
class CostLogger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _estimate(self, model: str, pt: int, ct: int) -> float:
        in_c, out_c = PRICES.get(model, PRICES["gpt-4o-mini"])
        return (pt/1000)*in_c + (ct/1000)*out_c

    def log(self, model: str, pt: int, ct: int, error: str | None = None):
        rec = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "model": model,
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "cost_usd": round(self._estimate(model, pt, ct), 6),
            "error": error,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def total_cost(self) -> float:
        if not self.path.exists():
            return 0.0
        total = 0.0
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    total += float(json.loads(line).get("cost_usd", 0.0))
                except Exception:
                    pass
        return total
