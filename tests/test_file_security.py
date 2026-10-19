from io import BytesIO

import pytest
from pypdf import PdfReader
from werkzeug.datastructures import FileStorage

from app.services.file_security import (
    MAX_PAGES,
    UploadRejected,
    sanitize_pdf,
    store_uploaded_pdf,
)
from pdf_samples import (
    PNG_BYTES,
    make_pdf,
    make_pdf_with_hidden_payload,
    make_pdf_with_javascript,
    make_pdf_with_open_action,
)

MAX_SIZE = 5 * 1024 * 1024


def upload(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=BytesIO(content), filename=filename)


# --- sanitize_pdf ---

def test_valid_pdf_is_accepted_and_still_readable():
    clean = sanitize_pdf(make_pdf(pages=2))

    assert clean.startswith(b"%PDF-")
    assert len(PdfReader(BytesIO(clean)).pages) == 2


def test_bytes_hidden_after_eof_are_removed():
    secret = b"SECRET-PAYLOAD-12345"

    clean = sanitize_pdf(make_pdf_with_hidden_payload(secret))

    assert secret not in clean


@pytest.mark.parametrize(
    "malicious", [make_pdf_with_javascript(), make_pdf_with_open_action()]
)
def test_pdf_with_active_content_is_rejected(malicious):
    with pytest.raises(UploadRejected):
        sanitize_pdf(malicious)


def test_png_is_not_a_pdf():
    with pytest.raises(UploadRejected):
        sanitize_pdf(PNG_BYTES)


def test_corrupted_pdf_is_rejected():
    with pytest.raises(UploadRejected):
        sanitize_pdf(b"%PDF-1.4 this is not really a pdf")


def test_too_many_pages_is_rejected():
    with pytest.raises(UploadRejected):
        sanitize_pdf(make_pdf(pages=MAX_PAGES + 1))


# --- store_uploaded_pdf ---

def test_valid_upload_is_saved_under_random_name(tmp_path):
    stored = store_uploaded_pdf(upload(make_pdf(), "talon.pdf"), tmp_path, MAX_SIZE)

    assert stored.stored_name != "talon.pdf"
    assert stored.stored_name.endswith(".pdf")
    assert (tmp_path / stored.stored_name).exists()
    assert stored.original_name == "talon.pdf"


def test_path_traversal_in_filename_is_neutralized(tmp_path):
    folder = tmp_path / "private"

    stored = store_uploaded_pdf(upload(make_pdf(), "../../evil.pdf"), folder, MAX_SIZE)

    assert stored.original_name == "evil.pdf"
    assert [p.name for p in folder.iterdir()] == [stored.stored_name]
    assert not (tmp_path / "evil.pdf").exists()


@pytest.mark.parametrize("filename", ["talon.exe", "talon.pdf.exe", "talon", "talon.png"])
def test_wrong_extension_is_rejected(tmp_path, filename):
    with pytest.raises(UploadRejected):
        store_uploaded_pdf(upload(make_pdf(), filename), tmp_path, MAX_SIZE)


def test_png_renamed_to_pdf_is_rejected(tmp_path):
    with pytest.raises(UploadRejected):
        store_uploaded_pdf(upload(PNG_BYTES, "fake.pdf"), tmp_path, MAX_SIZE)
    assert list(tmp_path.iterdir()) == []


def test_oversized_file_is_rejected(tmp_path):
    with pytest.raises(UploadRejected):
        store_uploaded_pdf(upload(make_pdf(), "big.pdf"), tmp_path, max_size=100)


def test_empty_file_is_rejected(tmp_path):
    with pytest.raises(UploadRejected):
        store_uploaded_pdf(upload(b"", "empty.pdf"), tmp_path, MAX_SIZE)