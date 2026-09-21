from pathlib import Path

from pypdf import PdfReader

from app.core.logging import get_logger
from app.models.document import RawPage

logger = get_logger(__name__)


def document_id_from_path(path: Path) -> str:
    """e.g. data/documents/hr/parental_leave_policy.pdf -> parental_leave_policy"""
    return path.stem


def department_from_path(path: Path, raw_docs_root: Path) -> str:
    """The department is the first sub-folder under the raw docs root,
    e.g. data/documents/hr/foo.pdf -> 'hr'. Falls back to 'unknown'."""
    try:
        relative = path.relative_to(raw_docs_root)
        return relative.parts[0] if len(relative.parts) > 1 else "unknown"
    except ValueError:
        return "unknown"


def load_pdf(path: Path, raw_docs_root: Path) -> list[RawPage]:
    """Extract text page-by-page from a single PDF."""
    reader = PdfReader(str(path))
    doc_id = document_id_from_path(path)
    department = department_from_path(path, raw_docs_root)
    document_name = doc_id.replace("_", " ").title()

    pages: list[RawPage] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(
            RawPage(
                document_id=doc_id,
                document_name=document_name,
                department=department,
                page=page_number,
                text=text,
            )
        )
    logger.info("Loaded %s (%d pages)", path.name, len(pages))
    return pages


def discover_pdfs(raw_docs_root: Path) -> list[Path]:
    """Recursively find every PDF under the raw docs root."""
    return sorted(raw_docs_root.rglob("*.pdf"))


def load_all_pdfs(raw_docs_root: Path) -> list[RawPage]:
    all_pages: list[RawPage] = []
    pdf_paths = discover_pdfs(raw_docs_root)
    if not pdf_paths:
        logger.warning("No PDFs found under %s", raw_docs_root)
    for path in pdf_paths:
        all_pages.extend(load_pdf(path, raw_docs_root))
    return all_pages
