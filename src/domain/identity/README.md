# Bounded Context: Identity

**Responsibility**: Authentication and authorization for tenant users (negocios). Manages the staff who log in to the dashboard, NOT the end clients chatting via WhatsApp.

## Aggregates

- **`User`** (root) — A person with login credentials, scoped to one tenant. A single human can have separate User accounts in multiple tenants.

## Value Objects

- `Email` — Validated email
- `PasswordHash` — Stored Argon2id hash
- `Role` — OWNER, ADMIN, STAFF, READONLY
- `Permission` — Fine-grained capabilities (compose at the role level)

## Events

- `UserCreated`, `UserLoggedIn`, `UserPasswordChanged`, `UserRoleChanged`

## Notes

- Implements Argon2id password hashing (port in application, impl in infrastructure)
- JWT issuance lives in infrastructure (`infrastructure/auth/`)
- Multi-tenancy: User belongs to exactly one tenant; tokens carry both `user_id` and `tenant_id` claims; the API resolves both on every request.
