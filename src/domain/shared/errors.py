from __future__ import annotations


class DomainError(Exception):
    """Base for all domain-level errors. These represent rule violations,
    not infrastructure failures."""


class NotFoundError(DomainError):
    """Aggregate not found within the current tenant scope."""


class ConflictError(DomainError):
    """Operation conflicts with current state (e.g. slot already booked)."""


class ValidationError(DomainError):
    """Input fails domain invariants."""


class TenantIsolationError(DomainError):
    """Attempt to operate across tenant boundaries. This is a security error."""


class BusinessRuleViolationError(DomainError):
    """Operation would violate an explicit business rule."""


class AuthenticationError(DomainError):
    """Credentials are invalid or the account cannot be authenticated."""
