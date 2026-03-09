from app.infrastructure.security.token_cipher import TokenCipher


def test_token_cipher_round_trip() -> None:
    cipher = TokenCipher()

    encrypted = cipher.encrypt("secret-token")

    assert encrypted != "secret-token"
    assert cipher.decrypt(encrypted) == "secret-token"
