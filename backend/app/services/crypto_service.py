"""Fernet-based encryption for site credentials."""
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class CryptoService:
    _fernet: Fernet | None = None

    @classmethod
    def _get_fernet(cls) -> Fernet:
        if cls._fernet is None:
            settings = get_settings()
            if not settings.MASTER_KEY:
                raise RuntimeError(
                    "MASTER_KEY not set in .env. Generate one with: "
                    "python -c \"from cryptography.fernet import Fernet; "
                    "print(Fernet.generate_key().decode())\""
                )
            cls._fernet = Fernet(settings.MASTER_KEY.encode())
        return cls._fernet

    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        return cls._get_fernet().encrypt(plaintext.encode()).decode()

    @classmethod
    def decrypt(cls, ciphertext: str) -> str:
        try:
            return cls._get_fernet().decrypt(ciphertext.encode()).decode()
        except InvalidToken as e:
            raise ValueError("Invalid ciphertext or wrong MASTER_KEY") from e
