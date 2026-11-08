"""Checks for an uploaded PDF, in this order:

1. Size: MAX_CONTENT_LENGTH (config.py) makes Flask refuse any request over 5 MB
   with 413 before our code runs.
2. Extension: only ".pdf".
3. Content: the file must really start like a PDF ("%PDF-"); a PNG renamed to
   .pdf fails here.
4. Active content: PDFs that can run JavaScript, launch programs or carry hidden
   attached files are refused.
5. Hidden content (steganography): the PDF is rebuilt from its pages only. Anything
   outside the pages (bytes after %%EOF, metadata, attachments) is not copied.
   This lowers the risk; it cannot prove that the page images hide nothing.
"""

import re
import uuid
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from app.exceptions import UploadRejected

PDF_START = b"%PDF-"
# PDF names that mean "run something" or "a file inside the file". The lookahead
# avoids false alarms on longer names that only start the same way (e.g. /JSFont).
ACTIVE_CONTENT = re.compile(rb"/(JS|JavaScript|OpenAction|Launch|EmbeddedFile|RichMedia)(?![A-Za-z0-9])")


def check_and_clean_pdf(filename: str, data: bytes) -> bytes:
    """Return a clean copy of the PDF, or raise UploadRejected with a message for the user."""
    if Path(filename).suffix.lower() != ".pdf":
        raise UploadRejected("Only .pdf files are allowed.")
    if not data:
        raise UploadRejected("The file is empty.")
    if not data.startswith(PDF_START):
        raise UploadRejected("The file is not a real PDF.")
    if ACTIVE_CONTENT.search(data):
        raise UploadRejected("The PDF contains active content (scripts, launch actions or embedded files).")

    try:
        pages = PdfReader(BytesIO(data)).pages
        if len(pages) == 0:
            raise UploadRejected("The PDF has no pages.")
        writer = PdfWriter()  # a brand-new, empty PDF
        for page in pages:
            new_page = writer.add_page(page)
            for key in ("/Annots", "/AA"):  # links, form fields and page actions
                if key in new_page:
                    del new_page[key]
        output = BytesIO()
        writer.write(output)
    except UploadRejected:
        raise
    except Exception as exc:  # pypdf raises many different errors on broken files
        raise UploadRejected("The PDF is damaged or cannot be read.") from exc
    return output.getvalue()


def save_pdf(content: bytes, folder: str) -> str:
    """Save under a new random name and return it. The user's file name is never
    used on disk, so names like "../../app.py" cannot write outside the folder."""
    Path(folder).mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.pdf"
    (Path(folder) / stored_name).write_bytes(content)
    return stored_name
