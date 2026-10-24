from io import BytesIO
from pathlib import Path

from app.models import AuditLog, SecureDocument
from pdf_samples import PNG_BYTES, make_pdf, make_pdf_with_javascript

PASSWORD = "parola-sigura-123"


def login(client, email="ana@gmail.com"):
    client.post("/register", data={"email": email, "phone": "0712345678", "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client


def post_file(client, content, filename):
    return client.post(
        "/documents/upload",
        data={"document": (BytesIO(content), filename)},
        content_type="multipart/form-data",
    )


def stored_files(app):
    folder = Path(app.config["UPLOAD_FOLDER"])
    return list(folder.iterdir()) if folder.exists() else []


def test_upload_requires_login(client):
    response = post_file(client, make_pdf(), "talon.pdf")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_valid_upload_is_saved_and_linked_to_user(app, client):
    login(client)

    response = post_file(client, make_pdf(), "talon.pdf")

    assert response.status_code == 302
    assert len(stored_files(app)) == 1
    with app.app_context():
        document = SecureDocument.query.one()
        assert document.original_filename == "talon.pdf"
        assert document.stored_filename != "talon.pdf"
        assert document.user_id == 1


def test_uploaded_document_appears_in_list(client):
    login(client)
    post_file(client, make_pdf(), "talon.pdf")

    html = client.get("/documents").get_data(as_text=True)

    assert "talon.pdf" in html


def test_upload_without_file_is_rejected(client):
    login(client)

    response = client.post("/documents/upload", data={}, content_type="multipart/form-data")

    assert response.status_code == 400


def test_wrong_extension_is_rejected(app, client):
    login(client)

    response = post_file(client, make_pdf(), "malware.exe")

    assert response.status_code == 400
    assert stored_files(app) == []


def test_fake_pdf_is_rejected(app, client):
    login(client)

    response = post_file(client, PNG_BYTES, "fake.pdf")

    assert response.status_code == 400
    assert stored_files(app) == []


def test_pdf_with_javascript_is_rejected(app, client):
    login(client)

    response = post_file(client, make_pdf_with_javascript(), "evil.pdf")

    assert response.status_code == 400
    assert stored_files(app) == []


def test_too_large_request_returns_413(app, client):
    login(client)
    app.config["MAX_CONTENT_LENGTH"] = 1000

    response = post_file(client, make_pdf(pages=5) + b"0" * 5000, "big.pdf")

    assert response.status_code == 413
    assert stored_files(app) == []


def test_owner_can_download_own_document(client):
    login(client)
    post_file(client, make_pdf(), "talon.pdf")

    response = client.get("/documents/1/download")

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF-")
    assert "attachment" in response.headers["Content-Disposition"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_other_user_cannot_download_document(app):
    owner = login(app.test_client(), "ana@gmail.com")
    post_file(owner, make_pdf(), "talon.pdf")
    intruder = login(app.test_client(), "ion@gmail.com")

    assert intruder.get("/documents/1/download").status_code == 404


def test_anonymous_cannot_download_document(app, client):
    owner = login(app.test_client())
    post_file(owner, make_pdf(), "talon.pdf")

    response = client.get("/documents/1/download")

    assert response.status_code == 302


def test_upload_events_are_audited(app, client):
    login(client)
    post_file(client, make_pdf(), "talon.pdf")
    post_file(client, PNG_BYTES, "fake.pdf")

    with app.app_context():
        events = [e.event_type for e in AuditLog.query.order_by(AuditLog.id)]

    assert "document_uploaded" in events
    assert "document_upload_rejected" in events


def test_owner_can_delete_document(app, client):
    login(client)
    post_file(client, make_pdf(), "talon.pdf")

    response = client.post("/documents/1/delete")

    assert response.status_code == 302
    assert stored_files(app) == []  # the file is gone from disk
    with app.app_context():
        assert SecureDocument.query.count() == 0


def test_deleted_document_cannot_be_downloaded(client):
    login(client)
    post_file(client, make_pdf(), "talon.pdf")
    client.post("/documents/1/delete")

    assert client.get("/documents/1/download").status_code == 404


def test_other_user_cannot_delete_document(app):
    owner = login(app.test_client(), "ana@gmail.com")
    post_file(owner, make_pdf(), "talon.pdf")
    intruder = login(app.test_client(), "ion@gmail.com")

    assert intruder.post("/documents/1/delete").status_code == 404
    assert len(stored_files(app)) == 1
    with app.app_context():
        assert SecureDocument.query.count() == 1


def test_anonymous_cannot_delete_document(app, client):
    owner = login(app.test_client())
    post_file(owner, make_pdf(), "talon.pdf")

    response = client.post("/documents/1/delete")

    assert response.status_code == 302
    assert len(stored_files(app)) == 1


def test_delete_requires_post(client):
    login(client)
    post_file(client, make_pdf(), "talon.pdf")

    assert client.get("/documents/1/delete").status_code == 405


def test_document_deletion_is_audited(app, client):
    login(client)
    post_file(client, make_pdf(), "talon.pdf")
    client.post("/documents/1/delete")

    with app.app_context():
        events = [e.event_type for e in AuditLog.query.order_by(AuditLog.id)]

    assert "document_deleted" in events