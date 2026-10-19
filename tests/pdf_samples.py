from io import BytesIO

from pypdf import PdfWriter


def make_pdf(pages: int = 1) -> bytes:
    """A small, valid, harmless PDF."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def make_pdf_with_javascript() -> bytes:
    """A valid PDF with a JavaScript action object appended (the kind of file we must reject)."""
    return make_pdf() + b"\n99 0 obj\n<< /S /JavaScript /JS (app.alert(1)) >>\nendobj\n"


def make_pdf_with_open_action() -> bytes:
    return make_pdf() + b"\n99 0 obj\n<< /OpenAction << /S /Launch >> >>\nendobj\n"


def make_pdf_with_hidden_payload(payload: bytes) -> bytes:
    """A valid PDF with extra bytes hidden after the %%EOF marker."""
    return make_pdf() + b"\n" + payload


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64