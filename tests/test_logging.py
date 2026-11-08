"""N7.01: user actions are written to a log file (logs/activity.log) that admins can read."""

from app.cli import create_admin

CREDENTIALS = {"email": "ana@gmail.com", "phone": "0712345678", "password": "parola-sigura-123"}
LOGIN = {"email": CREDENTIALS["email"], "password": CREDENTIALS["password"]}


def lines(log_text):
    return log_text().splitlines()


# --- one line per request ---


def test_page_view_is_logged_with_ip_user_path_and_status(client, log_text):
    client.get("/")

    assert lines(log_text)[-1].endswith("ip=127.0.0.1 user=- GET '/' status=200")


def test_logged_in_user_id_is_recorded(client, log_text):
    client.post("/register", data=CREDENTIALS)
    client.post("/login", data=LOGIN)

    client.get("/cart")

    assert "user=1 GET '/cart' status=200" in lines(log_text)[-1]


def test_error_status_is_logged(client, log_text):
    client.get("/product/does-not-exist")

    assert "status=404" in lines(log_text)[-1]


def test_static_files_are_not_logged(client, log_text):
    client.get("/static/img/placeholder.svg")

    assert log_text() == ""


def test_newlines_in_the_path_cannot_forge_log_lines(client, log_text):
    client.get("/x%0Aip=6.6.6.6%20user=1%20status=200")

    assert len(lines(log_text)) == 1  # the newline is written as the two characters \n


# --- one line per important action ---


def test_register_login_and_logout_are_logged(client, log_text):
    client.post("/register", data=CREDENTIALS)
    client.post("/login", data=LOGIN)
    client.post("/logout")

    events = [line.split("event=")[1].split()[0] for line in lines(log_text) if "event=" in line]
    assert events == ["user_registered", "login_success", "logout"]
    assert "user=1 event=login_success" in log_text()


def test_event_lines_never_end_with_a_space(client, log_text):
    """An event without details (logout) ends right after its name; one with details keeps them."""
    client.post("/register", data=CREDENTIALS)
    client.post("/login", data=LOGIN)
    client.post("/logout")

    event_lines = [line for line in lines(log_text) if "event=" in line]
    assert any(line.endswith("event=logout") for line in event_lines)
    assert not any(line.endswith(" ") for line in event_lines)


def test_failed_login_is_logged_with_ip_and_email(client, log_text):
    client.post("/login", data={"email": "nobody@gmail.com", "password": "x" * 10})

    assert "ip=127.0.0.1 user=- event=login_failed email='nobody@gmail.com'" in log_text()


def test_passwords_and_query_strings_are_never_logged(client, log_text):
    client.post("/register", data=CREDENTIALS)
    client.post("/login?session_id=cs_secret_123", data={"email": CREDENTIALS["email"], "password": "gresita-123"})

    text = log_text()
    assert CREDENTIALS["password"] not in text
    assert "gresita-123" not in text
    assert "cs_secret_123" not in text
    assert "POST '/login' status=401" in text


# --- the admin page that shows the file ---


def admin(app):
    with app.app_context():
        create_admin("boss@gmail.com", "0711111111", "parola-admin-123")
    client = app.test_client()
    client.post("/login", data={"email": "boss@gmail.com", "password": "parola-admin-123"})
    return client


def test_admin_reads_the_newest_lines_first(app, client):
    client.post("/login", data={"email": "first@gmail.com", "password": "x" * 10})
    client.post("/login", data={"email": "second@gmail.com", "password": "x" * 10})

    html = admin(app).get("/admin/log").get_data(as_text=True)

    assert html.index("second@gmail.com") < html.index("first@gmail.com")


def test_log_page_escapes_what_visitors_typed(app, client):
    client.post("/login", data={"email": "<script>alert(1)</script>", "password": "x" * 10})

    html = admin(app).get("/admin/log").get_data(as_text=True)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_customers_cannot_read_the_log(client):
    client.post("/register", data=CREDENTIALS)
    client.post("/login", data=LOGIN)

    assert client.get("/admin/log").status_code == 403
