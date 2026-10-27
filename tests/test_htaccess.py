from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_uploads_folder_has_a_deny_all_htaccess():
    rules = (ROOT / "private_uploads" / ".htaccess").read_text(encoding="utf-8")

    assert "Require all denied" in rules


def test_root_htaccess_protects_secrets_code_and_listings():
    rules = (ROOT / ".htaccess").read_text(encoding="utf-8")

    assert r"\.env" in rules
    assert "private_uploads" in rules
    assert "Options -Indexes" in rules
    assert "Require all denied" in rules


def test_uploads_are_not_reachable_through_the_web_app(client):
    assert client.get("/private_uploads/anything.pdf").status_code == 404
    assert client.get("/static/../private_uploads/x.pdf").status_code == 404