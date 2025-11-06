import os
import psycopg2
from pathlib import Path


def _dsn():
    dsn = os.getenv("POSTGRES_DSN")
    if dsn:
        return dsn
    host = os.getenv("POSTGRES_HOST", "db")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "talk_to_doc")
    user = os.getenv("POSTGRES_USER", "postgres")
    pwd = os.getenv("POSTGRES_PASSWORD", "postgres")
    return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"


def main():
    schema_path = Path(__file__).parent / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    conn = psycopg2.connect(_dsn())
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        print("✅ Database schema created/verified.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
