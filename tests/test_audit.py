from app.models import AuditLog, User

CREDENTIALS = {
    "email": "ana@gmail.com",
    "phone": "0712345678",
    "password": "parola-sigura-123",
}


def event_types(app):
    with app.app_context():
        return [e.event_type for e in AuditLog.query.order_by(AuditLog.id)]


def test_register_login_logout_are_saved_in_database(app, client):
    client.post("/register", data=CREDENTIALS)
    client.post("/login", data={"email": CREDENTIALS["email"], "password": CREDENTIALS["password"]})
    client.post("/logout")

    assert event_types(app) == ["user_registered", "login_success", "logout"]


def test_failed_login_is_saved_with_ip(app, client):
    client.post("/login", data={"email": "nobody@gmail.com", "password": "x" * 10})

    with app.app_context():
        entry = AuditLog.query.one()
        assert entry.event_type == "login_failed"
        assert entry.user_id is None
        assert entry.ip_address == "127.0.0.1"


def test_audit_entry_is_linked_to_user(app, client):
    client.post("/register", data=CREDENTIALS)

    with app.app_context():
        user = User.query.one()
        assert AuditLog.query.one().user_id == user.id