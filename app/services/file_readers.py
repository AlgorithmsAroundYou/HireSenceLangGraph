import os
from typing import Optional


def _read_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _read_pdf(path: str) -> str:
    try:
        import PyPDF2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyPDF2 is required to read PDF files") from exc

    text_parts: list[str] = []
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    return "\n".join(text_parts)


def _read_docx(path: str) -> str:
    try:
        import docx  # python-docx  # type: ignore
    except ImportError as exc:
        raise RuntimeError("python-docx is required to read DOCX files") from exc

    document = docx.Document(path)
    return "\n".join(para.text for para in document.paragraphs)


def _read_doc(path: str) -> str:
    """Best-effort .doc reader.

    Tries to use textract if available; otherwise raises an error.
    """

    try:
        import textract  # type: ignore
    except ImportError as exc:
        raise RuntimeError("textract is required to read DOC files") from exc

    content = textract.process(path)
    try:
        return content.decode("utf-8", errors="ignore")
    except Exception:
        return content.decode(errors="ignore")


def read_file_to_text(path: str) -> str:
    """Read a JD or resume file (txt, pdf, doc, docx) into plain text.

    Raises RuntimeError for unsupported extensions or missing parser libs.
    """

    _, ext = os.path.splitext(path)
    ext = (ext or "").lower().lstrip(".")

    if ext == "txt":
        return _read_txt(path)
    if ext == "pdf":
        return _read_pdf(path)
    if ext == "docx":
        return _read_docx(path)
    if ext == "doc":
        return _read_doc(path)

    raise RuntimeError(f"Unsupported file extension for text extraction: .{ext}")
