import pytest

from app.validators import is_valid_email, is_valid_password, is_valid_phone


@pytest.mark.parametrize("value", ["ana@gmail.com", "ion.popescu+shop@yahoo.com"])
def test_valid_emails(value):
    assert is_valid_email(value)


@pytest.mark.parametrize(
    "value", ["", "ana", "ana@", "@gmail.com", "ana@gmail", "an a@gmail.com"]
)
def test_invalid_emails(value):
    assert not is_valid_email(value)


def test_valid_phone():
    assert is_valid_phone("0712345678")


@pytest.mark.parametrize(
    "value", ["", "071234567", "07123456789", "07123abc78", "0712 345 678", "0712345678\n"]
)
def test_invalid_phones(value):
    assert not is_valid_phone(value)


def test_password_length():
    assert is_valid_password("12345678")
    assert not is_valid_password("1234567")