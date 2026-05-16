# Bounded Context: Business

**Responsibility**: The negotiated structures behind a tenant — locations, services offered, professionals, hours of operation, dynamic field configurations per industry.

## Aggregates

- **`Business`** (root) — A physical or logical location of the tenant. A tenant may have multiple businesses (multi-sucursal). Owns services, professionals, hours, and field configurations.

## Entities (inside the Business aggregate)

- `Service` — Offering with name, duration, price, optional professional restrictions
- `Professional` — Staff member, with assignable services and weekly availability
- `BusinessHours` — Per day-of-week open/close times
- `BusinessFieldConfig` — Custom field per industry (pet_name, vehicle_model, etc.)

## Value Objects

- `Industry` — Enum/registry of supported industries (hair_salon, veterinary, mechanic, clinic, gym, ...)
- `OperatingHour` — DayOfWeek + open + close + is_open
- `Duration` — Service duration with arithmetic (e.g. add buffer)

## Events

- `BusinessCreated`, `ServiceAdded`, `ProfessionalAssigned`, `HoursUpdated`

## Auto-provisioning

When a tenant completes onboarding for industry X, the application layer
seeds the Business with a **default template** of services and field
configurations (see `application/onboarding/industry_templates.py`).
This is what makes auto-onboarding turnkey.
