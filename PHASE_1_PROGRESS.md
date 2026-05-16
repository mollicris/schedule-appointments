# Phase 1 — Backend Implementation Progress

**Phase 1** targets the core booking flow: tenant registration, business/service management, appointment CRUD, and WhatsApp webhook integration.

## ✅ Completed (as of 2026-05-16)

### 1. Database Layer
- **ORM Models**: 10 models created in `src/infrastructure/persistence/models/`
  - `TenantModel` — tenant aggregate (not tenant-scoped)
  - `UserModel` — admin/staff accounts
  - `BusinessModel`, `ServiceModel`, `ProfessionalModel`, `BusinessHourModel` — business context
  - `AppointmentModel` — appointment CRUD
  - `ClientModel` — client profiles with WhatsApp integration
  - `ConversationModel`, `MessageModel` — conversation state + message history

- **Alembic Migration**: `001_initial_schema.py`
  - Creates all 9 tables
  - Enables pgvector extension for future embeddings
  - **Row-Level Security (RLS)** policies on all tenant-aware tables
    - SELECT/INSERT/UPDATE/DELETE filtered by `current_setting('app.current_tenant_id')`
    - Defense in depth: application + DB-level isolation

- **Database Indexes**:
  - Primary tenant FK indices for efficient filtering
  - Secondary indices on frequently queried fields (email, phone, whatsapp_number, scheduled_at)

### 2. Domain Layer
- **Value Objects**: Enums for business domain concepts
  - `TenantStatus`, `SubscriptionPlan` (tenant context)
  - `UserRole` (identity context)
  - `DayOfWeek`, `BusinessStatus` (business context)
  - `AppointmentStatus` (appointment context)
  - `ConversationState` — **21-state machine** (conversation context)

- **Aggregate Roots**: Already scaffolded
  - `Tenant` aggregate in `src/domain/tenant/tenant.py` with full lifecycle (register → verify → onboard → active)
  - Other aggregates (Business, Service, Appointment, Client, Conversation) scaffolded, awaiting implementation

### 3. Onboarding (Registration)
- **Use Case**: `RegisterTenantUseCase` fully implemented
  - Validates email uniqueness
  - Auto-resolves slug collisions (e.g., `salon-maria`, `salon-maria-2`, etc.)
  - Creates initial admin user with hashed password
  - Issues verification token
  - Emits `TenantRegistered` domain event

- **Ports (Adapters)**:
  - `PasswordHasher` → `Argon2PasswordHasher` (argon2-cffi)
  - `VerificationTokenService` → `RedisVerificationTokenService` (24h expiry)
  - `UserFactory` → `UserFactoryImpl` (creates admin user at registration)

- **Repository**: `TenantRepositoryImpl` with SQLAlchemy async
  - Methods: `get_by_id`, `get_by_slug`, `get_by_admin_email`, `slug_exists`, `email_exists`, `add`, `update`

- **API Endpoint**: `POST /api/v1/onboarding/register`
  - FastAPI with Pydantic validation (EmailStr, min/max lengths)
  - Error handling: 409 Conflict (duplicate email), 422 Validation Error, 400 Domain Error
  - Returns: `tenant_id`, `slug`, `verification_sent_to`

### 4. Infrastructure
- **Database**: Async SQLAlchemy session factory with connection pooling
- **Redis**: Client helper for cache/token storage (`src/infrastructure/cache/redis_client.py`)
- **Dependency Injection**: FastAPI `Depends()` with Annotated type hints
  - `get_db_session`, `get_password_hasher`, `get_verification_token_service`, `get_tenant_repository`, `get_user_factory`, `get_unit_of_work`

## 🔄 In Progress / Next Steps (Phase 1)

### 1. Tenant Verification (Email)
- [ ] `VerifyEmailUseCase` — consumes verification token, transitions status to ONBOARDING
- [ ] Email service adapter (send verification email on `TenantRegistered` event)
- [ ] `POST /api/v1/onboarding/verify/{token}` endpoint

### 2. Onboarding Wizard (8 Steps)
- [ ] Step 1: Business profile (name, phone, timezone, address)
- [ ] Step 2: Industry selection (salon, vet, mechanic, clinic, etc.)
- [ ] Step 3: Services CRUD (add initial services with durations)
- [ ] Step 4: Business hours setup (day-of-week schedules)
- [ ] Step 5: Professionals (staff accounts for the business)
- [ ] Step 6: Dynamic field configuration (pet_name for vets, vehicle_model for mechanics)
- [ ] Step 7: WhatsApp connection (paste phone number ID + access token)
- [ ] Step 8: Complete & activate bot
- [ ] Stateful endpoints: `GET /api/v1/onboarding/wizard/state`, `POST /api/v1/onboarding/wizard/step/{n}`

### 3. CRUD: Business, Service, Professional
- [ ] `src/domain/business/aggregates.py` — domain logic
- [ ] Repository implementations
- [ ] Use cases: CreateBusiness, UpdateBusiness, DeleteBusiness, etc.
- [ ] `POST/GET/PUT/DELETE /api/v1/businesses/{id}/services`
- [ ] `POST/GET/PUT/DELETE /api/v1/businesses/{id}/professionals`

### 4. WhatsApp Webhook & Verification
- [ ] `POST /webhooks/whatsapp` handler
- [ ] HMAC signature verification against `whatsapp_app_secret`
- [ ] Message ingestion: extract text/audio/image payloads
- [ ] Create Conversation + Message records
- [ ] Emit `MessageReceived` domain event

### 5. Agent State Machine (LangGraph)
- [ ] `src/infrastructure/ai/agent_graph.py` — 21-state machine
- [ ] Nodes: one per state (IDLE, EXTRACTING_ENTITIES, SELECTING_SERVICE, etc.)
- [ ] Edges: transitions based on user input + collected_data completeness
- [ ] Tool definitions (check_availability, book_appointment, cancel_appointment)
- [ ] Claude integration (Sonnet for reasoning, Haiku for fast ops)

### 6. Entity Extraction
- [ ] Claude tool calling to parse user messages into structured entities
- [ ] Recognize: service, date, time, professional preference, customer info
- [ ] Handle multi-lingual input (Spanish + Portuguese)

### 7. Date/Time Parser
- [ ] Flexible Spanish parser for "mañana", "próximo lunes", "el 5 a las 11", etc.
- [ ] Regional variants (es-MX, es-BO, es-AR, pt-BR)
- [ ] Return ISO 8601 date + HH:MM time

### 8. Appointment CRUD
- [ ] `BookAppointmentUseCase` — integrate with entity extraction, check availability, confirm
- [ ] `CancelAppointmentUseCase`
- [ ] `RescheduleAppointmentUseCase`
- [ ] Availability checker: respect business hours, service duration, booked slots

### 9. Reminders (Background Jobs)
- [ ] `arq` job queue setup
- [ ] `SendReminderJob` — 24h before appointment, with WhatsApp button confirmation
- [ ] Button actions: Confirm / Reschedule / Cancel

## 📋 Architecture Notes

### Multitenancy & Security
- **RLS at DB level**: Bugs in app code cannot leak data across tenants
- **TenantContext**: `ContextVar` propagates current tenant through request lifecycle
- **No tenant scoping for Tenant aggregate**: Registration/verification is global; only Business+ are scoped

### Mapper Pattern
- Domain entities ↔ ORM models via `*Mapper` classes
- Keeps domain logic pure; ORM is implementation detail
- Easy to swap SQLAlchemy for another DB library

### Event Sourcing (Future)
- Domain events (`TenantRegistered`, `AppointmentBooked`, etc.) currently discarded
- When implementing analytics/audit, migrate to event store in PostgreSQL

### DDD Bounded Contexts
- **tenant**: Aggregate root, lifecycle
- **onboarding**: Registration, verification, wizard
- **identity**: Users, roles, auth
- **business**: Businesses, services, professionals, hours
- **appointment**: Booking, availability, cancellation
- **client**: Client profiles, interaction history
- **conversation**: Chat state machine, escalation

## 🧪 Testing Readiness

**Unit tests** (no DB):
- Domain entities, value objects, use case logic
- Validation rules, state transitions

**Integration tests** (real DB):
- Migration rollback/forward
- RLS policy enforcement
- Repository operations with transaction isolation

**E2E tests**:
- Full registration → verification → onboarding → booking flow
- WhatsApp webhook ingest (mock Meta API)

## 📦 Dependencies Added

- `argon2-cffi` — password hashing
- `redis` (async) — tokens, cache
- `sqlalchemy` (2.0+) + `alembic` — ORM + migrations
- `anthropic` — Claude API (coming in agent phase)
- `langgraph` — state machine (coming in agent phase)

## 🚀 To Deploy Phase 1

```bash
# Install deps
cd backend-appointment
uv sync

# Run migrations (requires postgres + redis running)
uv run alembic upgrade head

# Start server
uv run uvicorn src.main:app --reload --port 8000

# Try registration
curl -X POST http://localhost:8000/api/v1/onboarding/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Salon María",
    "admin_email": "admin@salon.com",
    "admin_password": "securepass123",
    "industry": "hair_salon",
    "desired_slug": "salon-maria"
  }'
```

Expected response:
```json
{
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "slug": "salon-maria",
  "verification_sent_to": "admin@salon.com"
}
```
