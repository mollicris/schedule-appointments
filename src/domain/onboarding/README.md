# Bounded Context: Onboarding

**Responsibility**: The end-to-end self-service flow from "user clicks signup on landing page" to "bot is live and receiving WhatsApp messages". No human intervention required.

## Aggregates

- **`OnboardingSession`** (root) — Tracks the progress of a tenant through the wizard:
  1. Account created (email + password)
  2. Email verified
  3. Industry & business profile (name, timezone, phone)
  4. Services configured (or accepted from industry template)
  5. Business hours set
  6. WhatsApp Cloud API connected (Embedded Signup with Meta)
  7. Test message sent and received
  8. Bot live

## Value Objects

- `OnboardingStep` — Enum of the 8 steps above
- `OnboardingStatus` — IN_PROGRESS, COMPLETED, ABANDONED
- `IndustryTemplate` — Pre-defined bundle of services + dynamic fields per industry

## Events

- `OnboardingStarted`, `OnboardingStepCompleted`, `OnboardingAbandoned`, `OnboardingFinalized`

## Design intent

Onboarding is its own bounded context (separate from Tenant) because the
flow is **stateful and time-sensitive**: users can drop off, resume later,
or have steps fail (e.g. Meta verification rejected). Modeling it as an
aggregate lets us track per-step progress, abandonment metrics, and re-entry.

## Industry templates

The application layer holds the templates (a tenant who declares
"veterinary" auto-receives the default services like *Consulta general*,
*Vacunación*, etc. and the dynamic fields *pet_name*, *pet_type*, *reason*).
Templates live in `application/onboarding/industry_templates.py`.
