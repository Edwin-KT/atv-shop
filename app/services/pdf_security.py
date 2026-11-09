"""Checks for an uploaded PDF, in this order:

1. Size: MAX_CONTENT_LENGTH (config.py) makes Flask refuse any request over 5 MB
   with 413 before our code runs.
2. Extension: only ".pdf".
3. Content: the file must really start like a PDF ("%PDF-"); a PNG renamed to
   .pdf fails here.
4. Rebuild: a brand-new PDF is made from the pages only, without their links, form
   fields and page actions (/Annots, /AA). Everything else is simply not copied:
   JavaScript and actions that run when the file opens (/OpenAction), attachments,
   metadata, bytes after %%EOF (hidden content, steganography).

Why the bytes are not searched for names like /JS or /JavaScript: compressed images
and fonts look like random bytes and often contain those letters by chance, so a
search would refuse ordinary PDFs. The rebuild removes the real ones instead.

Limits: what is inside a page (its drawing, images and fonts) is copied as it is,
so this lowers the risk but cannot prove that a page image hides nothing.
"""

import uuid
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from app.exceptions import UploadRejected

PDF_START = b"%PDF-"


def check_and_clean_pdf(filename: str, data: bytes) -> bytes:
    """Return a clean copy of the PDF, or raise UploadRejected with a message for the user."""
    if Path(filename).suffix.lower() != ".pdf":
        raise UploadRejected("Only .pdf files are allowed.")
    if not data:
        raise UploadRejected("The file is empty.")
    if not data.startswith(PDF_START):
        raise UploadRejected("The file is not a real PDF.")

    try:
        pages = PdfReader(BytesIO(data)).pages
        if len(pages) == 0:
            raise UploadRejected("The PDF has no pages.")
        writer = PdfWriter()  # a brand-new, empty PDF
        for page in pages:
            # Removed BEFORE copying: add_page also copies every object the page
            # points to, so deleting them afterwards would leave them in the file.
            for key in ("/Annots", "/AA"):  # links, form fields and page actions
                if key in page:
                    del page[key]
            writer.add_page(page)
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
