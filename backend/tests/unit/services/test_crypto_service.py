"""crypto_service — Fernet round-trip on uye_kodu."""

from __future__ import annotations

import pytest

from app.services.crypto_service import CryptoService


def test_encrypt_decrypt_round_trip() -> None:
    plaintext = "FON5-SECRET-TOKEN-01234"
    token = CryptoService.encrypt(plaintext)

    assert token != plaintext
    assert CryptoService.decrypt(token) == plaintext


def test_encrypt_produces_different_tokens_each_call() -> None:
    """Fernet uses an IV; two encrypts of the same plaintext differ."""
    t1 = CryptoService.encrypt("hello")
    t2 = CryptoService.encrypt("hello")
    assert t1 != t2
    assert CryptoService.decrypt(t1) == "hello"
    assert CryptoService.decrypt(t2) == "hello"


def test_decrypt_rejects_invalid_token() -> None:
    with pytest.raises(ValueError, match="Invalid ciphertext"):
        CryptoService.decrypt("not-a-real-fernet-token")


def test_encrypt_handles_unicode() -> None:
    plaintext = "üye-kodu-şifreli-öğe"
    token = CryptoService.encrypt(plaintext)
    assert CryptoService.decrypt(token) == plaintext


def test_encrypt_empty_string() -> None:
    token = CryptoService.encrypt("")
    assert CryptoService.decrypt(token) == ""
