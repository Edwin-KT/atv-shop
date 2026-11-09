from pathlib import Path

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
from werkzeug.utils import secure_filename

from app.activity_log import log_event
from app.exceptions import UploadRejected
from app.extensions import db
from app.models import SecureDocument
from app.services.pdf_security import check_and_clean_pdf, save_pdf

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
        # file.read() is safe: MAX_CONTENT_LENGTH already limits the request to 5 MB.
        clean = check_and_clean_pdf(file.filename, file.read())
    except UploadRejected as exc:
        log_event("document_upload_rejected", details=str(exc))
        return _render_page([str(exc)], 400)

    document = SecureDocument(
        user_id=current_user.id,
        # Only for showing in the list: "../../x.pdf" becomes "x.pdf".
        original_filename=(secure_filename(file.filename) or "document.pdf")[:255],
        stored_filename=save_pdf(clean, current_app.config["UPLOAD_FOLDER"]),
        size_bytes=len(clean),
    )
    db.session.add(document)
    db.session.commit()

    log_event("document_uploaded", details=f"document_id={document.id}")
    flash("Document uploaded.", "success")
    return redirect(url_for("documents.list_documents"))


@bp.get("/documents/<int:document_id>/download")
@login_required
def download(document_id):
    document = db.session.get(SecureDocument, document_id)
    # 404 (not 403) for other people's files: we don't reveal that the id exists.
    if document is None or document.user_id != current_user.id:
        abort(404)

    # The row is in the database but the file can be gone: on Render the server's
    # disk is wiped on every deploy and restart. Say so instead of a bare 404.
    if not (Path(current_app.config["UPLOAD_FOLDER"]) / document.stored_filename).is_file():
        log_event("document_file_missing", details=f"document_id={document.id}")
        flash("This file is no longer stored on the server. "
              "Please delete it from the list and upload it again.", "warning")
        return redirect(url_for("documents.list_documents"))

    response = send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        document.stored_filename,
        mimetype="application/pdf",
        as_attachment=True,  # the browser downloads it instead of opening it
        download_name=document.original_filename,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@bp.post("/documents/<int:document_id>/delete")
@login_required
def delete(document_id):
    document = db.session.get(SecureDocument, document_id)
    if document is None or document.user_id != current_user.id:
        abort(404)

    deleted_id = document.id
    file_path = Path(current_app.config["UPLOAD_FOLDER"]) / document.stored_filename
    db.session.delete(document)
    db.session.commit()
    file_path.unlink(missing_ok=True)

    log_event("document_deleted", details=f"document_id={deleted_id}")
    flash("Document deleted.", "info")
    return redirect(url_for("documents.list_documents"))