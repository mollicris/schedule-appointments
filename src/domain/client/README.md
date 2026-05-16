# Bounded Context: Client

**Responsibility**: End customers of a tenant's business. Includes long-term memory for personalization (RAG), preference detection, no-show / churn predictions.

## Aggregates

- **`Client`** (root) — A person who has interacted with the bot (identified by phone). Owns their full interaction history summary.
- **`ClientMemory`** — Vectorized profile chunks for semantic recall. Loosely tied to Client; updated asynchronously by background jobs.

## Value Objects

- `PhoneNumber` — E.164 validated
- `Locale` — `es-BO`, `pt-BR`, etc.
- `RiskScore` — 0..1 for no-show / churn predictions
- `ClientPreferences` — Inferred (favorite professional, typical day/time)

## Events

- `ClientCreated` — First contact ever
- `ClientReturned` — Returning client recognized
- `ClientFlaggedHighNoShowRisk` — Triggers stronger confirmation flow
- `ClientChurnRiskDetected` — Triggers proactive outreach campaign

## Notes on multitenancy

A Client is **tenant-scoped**: the same phone number can be a Client of
multiple tenants (and the records are completely independent — different
preferences, different memory). Cross-tenant lookups are forbidden.
