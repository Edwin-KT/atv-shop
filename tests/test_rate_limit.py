import logging

from app.models import AuditLog


def test_request_101_in_a_minute_is_blocked(limited_app):
    client = limited_app.test_client()

    statuses = [client.get("/").status_code for _ in range(101)]

    assert statuses[:100] == [200] * 100
    assert statuses[100] == 429


def test_blocked_response_explains_and_has_retry_after(limited_app):
    client = limited_app.test_client()
    for _ in range(100):
        client.get("/")

    response = client.get("/")

    assert response.status_code == 429
    assert response.headers["Retry-After"]
    assert b"Too many requests" in response.data


def test_blocking_is_per_ip(limited_app):
    client = limited_app.test_client()
    for _ in range(101):
        client.get("/")

    other = limited_app.test_client()
    response = other.get("/", environ_overrides={"REMOTE_ADDR": "10.0.0.9"})

    assert response.status_code == 200


def test_static_files_do_not_use_the_limit(limited_app):
    client = limited_app.test_client()

    for _ in range(120):
        assert client.get("/static/img/placeholder.svg").status_code == 200

    assert client.get("/").status_code == 200


def test_health_endpoint_is_exempt(limited_app):
    client = limited_app.test_client()

    assert all(client.get("/health").status_code == 200 for _ in range(120))


def test_login_attempts_are_limited_more_strictly(limited_app):
    client = limited_app.test_client()
    data = {"email": "ana@gmail.com", "password": "gresita-123"}

    statuses = [client.post("/login", data=data).status_code for _ in range(11)]

    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429


def test_registration_attempts_are_limited(limited_app):
    client = limited_app.test_client()

    statuses = [client.post("/register", data={}).status_code for _ in range(6)]

    assert statuses[5] == 429


def test_blocking_is_audited_and_logged(limited_app, caplog):
    caplog.set_level(logging.INFO, logger="shop.access")
    client = limited_app.test_client()
    for _ in range(101):
        client.get("/")

    with limited_app.app_context():
        assert "rate_limited" in [e.event_type for e in AuditLog.query.all()]
    assert "status=429" in caplog.text


def test_limit_is_off_in_the_normal_test_app(client):
    assert all(client.get("/").status_code == 200 for _ in range(150))