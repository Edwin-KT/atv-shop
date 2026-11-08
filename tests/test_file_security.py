"""Unit tests for app/services/pdf_security.py: extension (N9.05), real content and
hidden content (N10.03). The 5 MB size limit (N9.04) is tested in test_documents.py."""

from io import BytesIO

import pytest
from pypdf import PdfReader

from app.exceptions import UploadRejected
from app.services.pdf_security import check_and_clean_pdf, save_pdf
from pdf_samples import (
    PNG_BYTES,
    make_pdf,
    make_pdf_with_hidden_payload,
    make_pdf_with_javascript,
    make_pdf_with_open_action,
)


def test_valid_pdf_is_accepted_and_still_readable():
    clean = check_and_clean_pdf("talon.pdf", make_pdf(pages=2))

    assert clean.startswith(b"%PDF-")
    assert len(PdfReader(BytesIO(clean)).pages) == 2


@pytest.mark.parametrize("filename", ["TALON.PDF", "scan.Pdf"])
def test_the_extension_check_ignores_upper_case(filename):
    assert check_and_clean_pdf(filename, make_pdf()).startswith(b"%PDF-")


@pytest.mark.parametrize("filename", ["talon.exe", "talon.pdf.exe", "talon", "talon.png"])
def test_only_pdf_extensions_are_accepted(filename):
    with pytest.raises(UploadRejected, match="Only .pdf"):
        check_and_clean_pdf(filename, make_pdf())


def test_png_renamed_to_pdf_is_rejected():
    """The extension says PDF, but the content does not start with %PDF-."""
    with pytest.raises(UploadRejected, match="not a real PDF"):
        check_and_clean_pdf("fake.pdf", PNG_BYTES)


def test_empty_file_is_rejected():
    with pytest.raises(UploadRejected, match="empty"):
        check_and_clean_pdf("empty.pdf", b"")


def test_bytes_hidden_after_eof_are_removed():
    secret = b"SECRET-PAYLOAD-12345"
    original = make_pdf_with_hidden_payload(secret)
    assert secret in original

    clean = check_and_clean_pdf("talon.pdf", original)

    assert secret not in clean


@pytest.mark.parametrize("malicious", [make_pdf_with_javascript(), make_pdf_with_open_action()])
def test_pdf_with_javascript_or_actions_is_rejected(malicious):
    with pytest.raises(UploadRejected, match="active content"):
        check_and_clean_pdf("evil.pdf", malicious)


def test_damaged_pdf_is_rejected():
    with pytest.raises(UploadRejected, match="damaged"):
        check_and_clean_pdf("broken.pdf", b"%PDF-1.4 this is not really a pdf")


def test_saved_file_gets_a_random_name_inside_the_folder(tmp_path):
    folder = tmp_path / "private"

    name = save_pdf(b"%PDF-clean", str(folder))

    assert name.endswith(".pdf") and len(name) == 36  # 32 hex characters + ".pdf"
    assert [p.name for p in folder.iterdir()] == [name]
    assert (folder / name).read_bytes() == b"%PDF-clean"
