"""INTEGRATION tests: uploading, downloading and deleting PDF documents through the
real routes.

Rubric: N2.02 use case "my documents"; N9.04 files over the limit (5 MB) are refused
with 413; N9.05 only real .pdf files; N10.03 what is stored is the cleaned copy
(hidden bytes and JavaScript removed); N4.02 UploadRejected is caught and shown to the user.
The checks themselves are unit-tested in tests/unit/test_pdf_security.py."""

from io import BytesIO
from pathlib import Path

import pytest

from app.models import SecureDocument
from helpers import page, register_and_login
from pdf_samples import (
    ACTIVE_NAMES,
    PNG_BYTES,
    make_large_pdf,
    make_pdf,
    make_pdf_with_hidden_payload,
    make_pdf_with_javascript,
)


@pytest.fixture()
def customer(client):
    return register_and_login(client)


def upload(client, content, filename):
    return client.post(
        "/documents/upload",
        data={"document": (BytesIO(content), filename)},
        content_type="multipart/form-data",
    )


def stored_files(app):
    folder = Path(app.config["UPLOAD_FOLDER"])
    return list(folder.iterdir()) if folder.exists() else []


def test_upload_requires_login(client):
    response = upload(client, make_pdf(), "talon.pdf")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_a_valid_pdf_is_saved_linked_to_its_owner_and_listed(app, customer):
    response = upload(customer, make_pdf(), "talon.pdf")

    assert response.status_code == 302
    assert len(stored_files(app)) == 1
    with app.app_context():
        document = SecureDocument.query.one()
        assert document.original_filename == "talon.pdf"
        assert document.stored_filename != "talon.pdf"  # a random name on disk
        assert document.user_id == 1
    assert "talon.pdf" in page(customer, "/documents")


def test_a_file_over_the_size_limit_gets_413(app, customer):
    app.config["MAX_CONTENT_LENGTH"] = 1000  # the real limit is 5 MB; a small one keeps the test fast

    response = upload(customer, make_pdf(pages=5) + b"0" * 5000, "big.pdf")

    assert response.status_code == 413
    assert b"Uploads are limited to" in response.data
    assert stored_files(app) == []


def test_a_png_renamed_to_pdf_is_refused_and_not_stored(app, customer):
    response = upload(customer, PNG_BYTES, "fake.pdf")

    assert response.status_code == 400
    assert b"The file is not a real PDF." in response.data
    assert stored_files(app) == []


def test_a_wrong_extension_is_refused(app, customer):
    response = upload(customer, make_pdf(), "malware.exe")

    assert response.status_code == 400
    assert stored_files(app) == []


def test_a_pdf_with_javascript_is_stored_without_it(app, customer):
    response = upload(customer, make_pdf_with_javascript(), "evil.pdf")

    assert response.status_code == 302  # accepted: the cleaned copy is kept
    (stored,) = stored_files(app)
    for name in ACTIVE_NAMES:
        assert name not in stored.read_bytes(), name


def test_a_large_pdf_under_the_limit_is_accepted(app, customer):
    pdf, _ = make_large_pdf()  # about 4.5 MB of image data, like a scan

    response = upload(customer, pdf, "scan.pdf")

    assert response.status_code == 302
    assert len(stored_files(app)) == 1
    assert "scan.pdf" in page(customer, "/documents")


def test_the_stored_file_is_the_cleaned_copy(app, customer):
    upload(customer, make_pdf_with_hidden_payload(b"SECRET-PAYLOAD-12345"), "talon.pdf")

    (stored,) = stored_files(app)
    assert stored.read_bytes().startswith(b"%PDF-")
    assert b"SECRET-PAYLOAD-12345" not in stored.read_bytes()


def test_a_file_name_with_folders_cannot_escape_the_upload_folder(app, customer, tmp_path):
    upload(customer, make_pdf(), "../../evil.pdf")

    assert len(stored_files(app)) == 1  # inside UPLOAD_FOLDER, under a random name
    assert not (tmp_path / "evil.pdf").exists()
    with app.app_context():
        assert SecureDocument.query.one().original_filename == "evil.pdf"


def test_an_upload_without_a_file_is_refused(customer):
    response = customer.post("/documents/upload", data={}, content_type="multipart/form-data")

    assert response.status_code == 400


def test_the_owner_downloads_the_pdf_as_an_attachment(customer):
    upload(customer, make_pdf(), "talon.pdf")

    response = customer.get("/documents/1/download")

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF-")
    assert "attachment" in response.headers["Content-Disposition"]  # downloaded, not opened


def test_the_owner_deletes_the_document_and_its_file(app, customer):
    upload(customer, make_pdf(), "talon.pdf")

    assert customer.get("/documents/1/delete").status_code == 405  # needs a POST
    customer.post("/documents/1/delete")

    assert stored_files(app) == []
    assert customer.get("/documents/1/download").status_code == 404
    with app.app_context():
        assert SecureDocument.query.count() == 0


def test_a_missing_file_gives_a_clear_message_and_can_still_be_deleted(app, customer, log_text):
    """On Render the disk is wiped on every deploy; the database row stays."""
    upload(customer, make_pdf(), "talon.pdf")
    (stored,) = stored_files(app)
    stored.unlink()

    response = customer.get("/documents/1/download")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/documents")
    assert "no longer stored on the server" in page(customer, "/documents")
    assert "event=document_file_missing" in log_text()

    customer.post("/documents/1/delete")
    assert "talon.pdf" not in page(customer, "/documents")
