from __future__ import annotations

import argon2

from src.application.onboarding.register_tenant import PasswordHasher as PasswordHasherPort


class Argon2PasswordHasher:
    """Adapter: implements PasswordHasher port using argon2."""

    def __init__(self) -> None:
        self._hasher = argon2.PasswordHasher()

    def hash(self, plaintext: str) -> str:
        """Hash plaintext password using Argon2."""
        return self._hasher.hash(plaintext)

    def verify(self, plaintext: str, hashed: str) -> bool:
        """Verify plaintext against Argon2 hash."""
        try:
            self._hasher.verify(hashed, plaintext)
            return True
        except (argon2.exceptions.VerifyMismatchError, argon2.exceptions.InvalidHashError):
            return False
