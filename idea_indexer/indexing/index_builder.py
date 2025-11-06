import joblib
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from idea_indexer.utils.jsonl import read_jsonl


# Build TF-IDF index from extracted text pages and fit a TF-IDF model.
def build_index(pages_jsonl: Path, tfidf_pkl: Path):
    docs = list(read_jsonl(pages_jsonl))
    texts = [d["text"] for d in docs]
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(texts)
    joblib.dump((vectorizer, X), tfidf_pkl)
