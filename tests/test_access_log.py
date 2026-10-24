import logging

PASSWORD = "parola-sigura-123"


def access_lines(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "shop.access"]


def test_page_view_is_logged(client, caplog):
    caplog.set_level(logging.INFO, logger="shop.access")

    client.get("/")

    lines = access_lines(caplog)
    assert len(lines) == 1
    assert "method=GET" in lines[0]
    assert "path='/'" in lines[0]
    assert "status=200" in lines[0]
    assert "user=-" in lines[0]
    assert "duration_ms=" in lines[0]


def test_logged_in_user_id_is_recorded(client, caplog):
    client.post("/register", data={"email": "ana@gmail.com", "phone": "0712345678", "password": PASSWORD})
    client.post("/login", data={"email": "ana@gmail.com", "password": PASSWORD})
    caplog.set_level(logging.INFO, logger="shop.access")

    client.get("/cart")

    assert "user=1" in access_lines(caplog)[-1]


def test_error_status_is_logged(client, caplog):
    caplog.set_level(logging.INFO, logger="shop.access")

    client.get("/product/does-not-exist")

    assert "status=404" in access_lines(caplog)[0]


def test_passwords_and_query_strings_are_never_logged(client, caplog):
    caplog.set_level(logging.DEBUG)

    client.post(
        "/login?session_id=cs_secret_123",
        data={"email": "ana@gmail.com", "password": "super-secret-pass"},
    )

    assert "super-secret-pass" not in caplog.text
    assert "cs_secret_123" not in caplog.text
    assert "path='/login'" in caplog.text


def test_static_files_are_not_logged(client, caplog):
    caplog.set_level(logging.INFO, logger="shop.access")

    client.get("/static/img/placeholder.svg")

    assert access_lines(caplog) == []


def test_newlines_in_path_cannot_forge_log_lines(client, caplog):
    caplog.set_level(logging.INFO, logger="shop.access")

    client.get("/x%0Aip=6.6.6.6%20user=1%20status=200")

    lines = access_lines(caplog)
    assert len(lines) == 1
    assert "\n" not in lines[0]