from pathlib import Path
import fitz


# Extract text from each page of a PDF file (PyMuPDF).
def extract_pdf_pages(path: Path):
    with fitz.open(str(path)) as doc:
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            yield i, text
