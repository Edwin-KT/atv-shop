"""UNIT tests for app/services/pdf_security.py: check_and_clean_pdf() and save_pdf(),
called directly with bytes (no HTTP).

Rubric: N9.05 only approved extensions (.pdf) and real PDF content; N10.03 hidden
content (steganography) and active content (JavaScript, actions) removed by rebuilding
the PDF; N4.02 the UploadRejected exception; N6.01 unit tests. The 5 MB limit (N9.04)
is an integration test, because Flask enforces it on the request
(tests/integration/test_documents.py)."""

from io import BytesIO

import pytest
from pypdf import PdfReader

from app.exceptions import UploadRejected
from app.services.pdf_security import check_and_clean_pdf, save_pdf
from pdf_samples import (
    ACTIVE_NAMES,
    PNG_BYTES,
    make_large_pdf,
    make_pdf,
    make_pdf_with_hidden_payload,
    make_pdf_with_javascript,
)


def test_a_valid_pdf_is_accepted_and_still_readable():
    clean = check_and_clean_pdf("talon.pdf", make_pdf(pages=2))

    assert clean.startswith(b"%PDF-")
    assert len(PdfReader(BytesIO(clean)).pages) == 2


def test_the_extension_check_ignores_upper_case():
    assert check_and_clean_pdf("TALON.PDF", make_pdf()).startswith(b"%PDF-")


@pytest.mark.parametrize("filename", ["talon.exe", "talon.pdf.exe", "talon", "talon.png"])
def test_only_pdf_extensions_are_accepted(filename):
    with pytest.raises(UploadRejected, match="Only .pdf"):
        check_and_clean_pdf(filename, make_pdf())


def test_png_renamed_to_pdf_is_rejected():
    """The name says PDF, but the content does not start with %PDF-."""
    with pytest.raises(UploadRejected, match="not a real PDF"):
        check_and_clean_pdf("fake.pdf", PNG_BYTES)


def test_an_empty_file_is_rejected():
    with pytest.raises(UploadRejected, match="empty"):
        check_and_clean_pdf("empty.pdf", b"")


def test_bytes_hidden_after_eof_are_removed():
    secret = b"SECRET-PAYLOAD-12345"
    original = make_pdf_with_hidden_payload(secret)
    assert secret in original

    assert secret not in check_and_clean_pdf("talon.pdf", original)


def test_javascript_and_actions_are_removed_from_the_saved_file():
    original = make_pdf_with_javascript()
    # The sample really is dangerous: a PDF reader finds the actions in the document.
    reader = PdfReader(BytesIO(original))
    assert "/OpenAction" in reader.trailer["/Root"]
    assert "/AA" in reader.pages[0] and "/Annots" in reader.pages[0]

    clean = check_and_clean_pdf("evil.pdf", original)

    for name in ACTIVE_NAMES:
        assert name not in clean, name
    assert len(PdfReader(BytesIO(clean)).pages) == 1  # the page itself is kept


def test_a_large_pdf_with_image_data_is_accepted():
    """Image bytes that contain /JavaScript by chance are not a reason to refuse."""
    original, image_bytes = make_large_pdf()
    assert 4_000_000 < len(original) < 5 * 1024 * 1024

    clean = check_and_clean_pdf("scan.pdf", original)

    assert len(PdfReader(BytesIO(clean)).pages) == 1
    assert image_bytes in clean  # the page image is copied whole


def test_a_damaged_pdf_is_rejected():
    with pytest.raises(UploadRejected, match="damaged"):
        check_and_clean_pdf("broken.pdf", b"%PDF-1.4 this is not really a pdf")


def test_the_saved_file_gets_a_random_name_inside_the_folder(tmp_path):
    folder = tmp_path / "private"

    name = save_pdf(b"%PDF-clean", str(folder))

    assert name.endswith(".pdf") and len(name) == 36  # 32 hex characters + ".pdf"
    assert [p.name for p in folder.iterdir()] == [name]
