"""
File parsing service.
Handles: PDF, DOCX, TXT, images (PNG/JPG/WEBP), CSV
Returns extracted text or base64 for images.
"""
import os
import base64
import io
from pathlib import Path
from typing import Tuple


def parse_file(filename: str, file_bytes: bytes) -> Tuple[str, str, str]:
    """Returns: (extracted_text, image_b64_or_empty, mime_type)"""
    ext = Path(filename).suffix.lower()

    if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        b64 = base64.b64encode(file_bytes).decode()
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}.get(ext, "image/jpeg")
        return "", b64, mime

    if ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            pages = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pages.append(f"[Page {i+1}]\n{text.strip()}")
            extracted = "\n\n".join(pages)
            if not extracted.strip():
                return "[PDF has no extractable text - may be scanned]", "", "application/pdf"
            return extracted[:8000], "", "application/pdf"
        except ImportError:
            return "[pypdf not installed - run: pip install pypdf]", "", "application/pdf"
        except Exception as e:
            return f"[PDF parse error: {e}]", "", "application/pdf"

    if ext in (".docx", ".doc"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            parts = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
                    if row_text:
                        parts.append(row_text)
            return "\n".join(parts)[:8000], "", "application/docx"
        except ImportError:
            return "[python-docx not installed - run: pip install python-docx]", "", "application/docx"
        except Exception as e:
            return f"[DOCX parse error: {e}]", "", "application/docx"

    if ext == ".csv":
        try:
            import csv
            text = file_bytes.decode("utf-8", errors="replace")
            rows = list(csv.reader(io.StringIO(text)))
            lines = [" | ".join(row) for row in rows[:50]]
            result = f"CSV ({len(rows)} rows):\n" + "\n".join(lines)
            if len(rows) > 50:
                result += f"\n... +{len(rows)-50} more rows"
            return result[:6000], "", "text/csv"
        except Exception as e:
            return f"[CSV parse error: {e}]", "", "text/csv"

    text_exts = {".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
                 ".html", ".css", ".xml", ".sh", ".log", ".rs", ".go", ".java", ".c", ".cpp"}
    if ext in text_exts or ext == "":
        try:
            return file_bytes.decode("utf-8", errors="replace")[:8000], "", "text/plain"
        except Exception as e:
            return f"[Text parse error: {e}]", "", "text/plain"

    return f"[Unsupported file type: {ext}]", "", "application/octet-stream"


def format_file_context(filename: str, text: str) -> str:
    return f'The user uploaded "{filename}".\n\nFile contents:\n---\n{text}\n---\n\nAnswer based on this file.'
