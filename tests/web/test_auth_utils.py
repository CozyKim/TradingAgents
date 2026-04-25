from tradingagents_web.auth import (
    generate_session_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password() -> None:
    password = "correct horse battery staple"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong", hashed) is False


def test_session_token_is_random() -> None:
    a = generate_session_token()
    b = generate_session_token()
    assert a != b
    assert len(a) >= 32  # at least 32 chars of entropy
