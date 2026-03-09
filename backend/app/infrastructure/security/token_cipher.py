import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


class TokenCipher:
    def __init__(self) -> None:
        digest = hashlib.sha256(settings.session_secret_key.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
        self._fernet = Fernet(key)

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
