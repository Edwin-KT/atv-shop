import re
import uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {".pdf"}
PDF_MAGIC = b"%PDF-"
MAX_PAGES = 20

# PDF names that mean "run something" or "hide a file inside".
# The lookahead stops false positives such as the font name /JSFont.
DANGEROUS_PDF_NAMES = re.compile(
    rb"/(JS|JavaScript|OpenAction|Launch|EmbeddedFile|RichMedia)(?![A-Za-z0-9])"
)


class UploadRejected(Exception):
    """Raised when an uploaded file fails a check. The message is safe to show to the user."""


@dataclass
class StoredFile:
    stored_name: str
    original_name: str
    size_bytes: int


def sanitize_pdf(raw: bytes) -> bytes:
    """Reject suspicious PDFs and rebuild the accepted ones from scratch.

    Only the pages are copied into a brand-new file. Document-level actions,
    embedded files, metadata and any bytes appended after %%EOF are dropped.
    Page annotations and page-level actions are removed explicitly.
    This reduces the risk; it does not make it zero.
    """
    if not raw.startswith(PDF_MAGIC):
        raise UploadRejected("The file is not a real PDF.")

    if DANGEROUS_PDF_NAMES.search(raw):
        raise UploadRejected(
            "The PDF contains active content (scripts, launch actions or embedded files)."
        )

    try:
        reader = PdfReader(BytesIO(raw))
        if reader.is_encrypted:
            raise UploadRejected("Encrypted PDFs are not accepted.")

        page_count = len(reader.pages)
        if page_count == 0 or page_count > MAX_PAGES:
            raise UploadRejected(f"The PDF must have between 1 and {MAX_PAGES} pages.")

        writer = PdfWriter()
        for page in reader.pages:
            new_page = writer.add_page(page)
            for key in ("/Annots", "/AA"):  # links, form widgets, page actions
                if key in new_page:
                    del new_page[key]

        output = BytesIO()
        writer.write(output)
    except UploadRejected:
        raise
    except Exception as exc:  # pypdf raises many error types on malformed input
        raise UploadRejected("The PDF is corrupted or cannot be processed.") from exc

    clean = output.getvalue()
    if not clean.startswith(PDF_MAGIC) or DANGEROUS_PDF_NAMES.search(clean):
        raise UploadRejected("The PDF could not be sanitized.")
    return clean


def save_private_file(content: bytes, upload_dir: str | Path) -> str:
    """Write the file under a random name; the user's filename is never used on disk."""
    folder = Path(upload_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.pdf"
    (folder / stored_name).write_bytes(content)
    return stored_name


def store_uploaded_pdf(file_storage, upload_dir: str | Path, max_size: int) -> StoredFile:
    """Run every check, sanitize, and save. Raises UploadRejected on any failure."""
    submitted_name = file_storage.filename or ""

    if Path(submitted_name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise UploadRejected("Only .pdf files are allowed.")

    raw = file_storage.read(max_size + 1)  # never read more than the limit + 1 byte
    if not raw:
        raise UploadRejected("The file is empty.")
    if len(raw) > max_size:
        raise UploadRejected(f"The file is larger than {max_size // (1024 * 1024)} MB.")

    clean = sanitize_pdf(raw)
    stored_name = save_private_file(clean, upload_dir)

    display_name = secure_filename(submitted_name) or "document.pdf"
    return StoredFile(stored_name, display_name[:255], len(clean))