CREATE TABLE IF NOT EXISTS pages (
    id SERIAL PRIMARY KEY,
    project_id TEXT,
    project_title TEXT,
    file_path TEXT,
    page INTEGER,
    text TEXT
);

ALTER TABLE pages
    ADD CONSTRAINT pages_unique_triplet
    UNIQUE (project_id, file_path, page);

CREATE TABLE IF NOT EXISTS page_vectors (
    page_id INTEGER PRIMARY KEY REFERENCES pages(id),
    vector FLOAT8[]
);

CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    project_title TEXT,
    start_date TEXT,
    end_date TEXT,
    work_summary TEXT
);

CREATE TABLE IF NOT EXISTS key_dates (
    id BIGSERIAL PRIMARY KEY,
    project_id TEXT REFERENCES projects(project_id) ON DELETE CASCADE,
    label TEXT,
    date_val TEXT,
    source_file TEXT,
    page TEXT
);

CREATE TABLE IF NOT EXISTS contacts (
    id BIGSERIAL PRIMARY KEY,
    project_id TEXT REFERENCES projects(project_id) ON DELETE CASCADE,
    name TEXT,
    role TEXT,
    email_addr TEXT,
    phone TEXT
);

CREATE TABLE IF NOT EXISTS keywords (
    id BIGSERIAL PRIMARY KEY,
    project_id TEXT REFERENCES projects(project_id) ON DELETE CASCADE,
    keyword TEXT,
    weight REAL
);

CREATE TABLE IF NOT EXISTS evidence (
    id BIGSERIAL PRIMARY KEY,
    project_id TEXT REFERENCES projects(project_id) ON DELETE CASCADE,
    file_path TEXT,
    page TEXT,
    snippet TEXT,
    score REAL
);
