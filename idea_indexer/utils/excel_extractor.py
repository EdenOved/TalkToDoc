from pathlib import Path
import pandas as pd


# Extracts text rows from all sheets in an Excel file.
def extract_excel(file_path: Path):
    xls = pd.ExcelFile(file_path)
    for sheet in xls.sheet_names:
        df = xls.parse(sheet).fillna("")
        for row_idx, row in df.iterrows():
            parts = [str(v).strip() for v in row.values if str(v).strip()]
            if not parts:
                continue
            text = " ".join(parts)
            yield {
                "file_path": str(file_path),
                "text": text,
                "source": "excel",
                "sheet": sheet,
                "row": row_idx + 1,
            }
