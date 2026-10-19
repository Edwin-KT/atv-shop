import logging

CREDENTIALS = {
    "email": "ana@gmail.com",
    "phone": "0712345678",
    "password": "parola-sigura-123",
}


def test_register_and_login_are_logged(client, caplog):
    caplog.set_level(logging.INFO)

    client.post("/register", data=CREDENTIALS)
    client.post("/login", data={"email": CREDENTIALS["email"], "password": "gresita-123"})

    assert "event=user_registered" in caplog.text
    assert "event=login_failed" in caplog.text


def test_password_is_never_logged(client, caplog):
    caplog.set_level(logging.DEBUG)

    client.post("/register", data=CREDENTIALS)
    client.post("/login", data={"email": CREDENTIALS["email"], "password": "gresita-123"})

    assert CREDENTIALS["password"] not in caplog.text
    assert "gresita-123" not in caplog.text