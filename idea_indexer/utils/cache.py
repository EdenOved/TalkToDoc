import hashlib
from pathlib import Path


# File-based cache storing JSON/text by hashed key.
class SimpleCache:
    def __init__(self, dirpath: Path):
        self.dir = Path(dirpath)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.dir / f"{h}.json"

    def get(self, key: str) -> str | None:
        p = self._path(key)
        return p.read_text(encoding="utf-8") if p.exists() else None

    def set(self, key: str, value: str):
        self._path(key).write_text(value, encoding="utf-8")
