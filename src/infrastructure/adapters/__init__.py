"""Adapters implementing ports from the application layer.

Adapters translate between application (domain) interfaces and
external dependencies (infrastructure). Examples:
  - PasswordHasher → Argon2PasswordHasher
  - VerificationTokenService → RedisVerificationTokenService
  - UserFactory → UserFactoryImpl
"""
