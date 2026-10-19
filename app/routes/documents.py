from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required

from app.extensions import db
from app.models import SecureDocument
from app.services.audit import record_event
from app.services.file_security import UploadRejected, store_uploaded_pdf

bp = Blueprint("documents", __name__)


def _render_page(errors=None, status=200):
    documents = (
        SecureDocument.query.filter_by(user_id=current_user.id)
        .order_by(SecureDocument.created_at.desc())
        .all()
    )
    return render_template("documents.html", documents=documents, errors=errors or []), status


@bp.get("/documents")
@login_required
def list_documents():
    return _render_page()


@bp.post("/documents/upload")
@login_required
def upload():
    file = request.files.get("document")
    if file is None or not file.filename:
        return _render_page(["Please choose a PDF file."], 400)

    try:
        stored = store_uploaded_pdf(
            file,
            current_app.config["UPLOAD_FOLDER"],
            current_app.config["MAX_CONTENT_LENGTH"],
        )
    except UploadRejected as exc:
        record_event("document_upload_rejected", user_id=current_user.id, details=str(exc))
        return _render_page([str(exc)], 400)

    document = SecureDocument(
        user_id=current_user.id,
        original_filename=stored.original_name,
        stored_filename=stored.stored_name,
        size_bytes=stored.size_bytes,
    )
    db.session.add(document)
    db.session.commit()

    record_event("document_uploaded", user_id=current_user.id, details=f"document_id={document.id}")
    flash("Document uploaded.", "success")
    return redirect(url_for("documents.list_documents"))


@bp.get("/documents/<int:document_id>/download")
@login_required
def download(document_id):
    document = db.session.get(SecureDocument, document_id)
    # 404 (not 403) for other people's files: we don't reveal that the id exists.
    if document is None or document.user_id != current_user.id:
        abort(404)

    response = send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        document.stored_filename,
        mimetype="application/pdf",
        as_attachment=True,  # the browser downloads it instead of opening it
        download_name=document.original_filename,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response