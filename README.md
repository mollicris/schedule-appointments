# Agente Citas — Backend

API REST y orquestación de IA para la plataforma multi-tenant de agendamiento por WhatsApp.

## Stack

- **Python 3.12** + **FastAPI** (async)
- **PostgreSQL 16 + pgvector** (multi-tenant con Row-Level Security)
- **SQLAlchemy 2.0** (async) + **Alembic**
- **Redis 7** (cache, queues con `arq`)
- **Anthropic Claude** (Sonnet 4.6 razonamiento, Haiku 4.5 tareas rápidas)
- **LangGraph** (state machine del agente)
- **Voyage AI** (embeddings multilingüe) + **Whisper** (audio)
- **uv** (gestor de paquetes)

## Arquitectura — DDD + SOLID

Cuatro capas concéntricas con regla de dependencia estricta:

```
┌──────────────────────────────────────────────┐
│  presentation/   FastAPI routers, webhooks    │
│  ┌────────────────────────────────────────┐  │
│  │  application/   Use cases, DTOs         │  │
│  │  ┌──────────────────────────────────┐  │  │
│  │  │  domain/   Entidades, VOs, eventos│  │  │ ← núcleo puro
│  │  └──────────────────────────────────┘  │  │
│  │  infrastructure/   DB, IA, WhatsApp     │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

### Bounded contexts

| Contexto | Responsabilidad |
|----------|-----------------|
| `tenant` | Aggregate raíz del tenant + lifecycle + planes |
| `onboarding` | Auto-onboarding (signup → wizard → bot activo) |
| `identity` | Users + roles + autenticación |
| `business` | Sucursales, servicios, profesionales, horarios |
| `appointment` | Booking, slots, cancelaciones |
| `client` | Clientes finales + memoria a largo plazo + predicciones |
| `conversation` | State machine del agente, mensajes, escalamiento |

### Multitenancy

- **Shared schema** con `tenant_id` en cada tabla
- **PostgreSQL Row-Level Security** filtra automáticamente por tenant
- `TenantContext` via `ContextVar` propaga el tenant actual a través de la request
- Defensa en profundidad: bugs de aplicación no leakean datos (RLS lo bloquea a nivel DB)

## Setup local

```bash
# Requisitos: Python 3.12, uv, Docker
pip install uv

# Servicios
docker-compose up -d

# Backend
cp .env.example .env  # editar con tus credenciales reales
uv sync
uv run alembic upgrade head      # cuando existan migraciones
uv run uvicorn src.main:app --reload --port 8000
```

API: `http://localhost:8000`
Docs interactivas: `http://localhost:8000/docs`

## Estructura

```
backend/
├── src/
│   ├── domain/             Núcleo DDD (sin deps externas)
│   │   ├── shared/         Base classes (Entity, AggregateRoot, ValueObject)
│   │   └── <contexto>/     Un folder por bounded context
│   ├── application/        Use cases por contexto
│   ├── infrastructure/     SQLAlchemy, Claude, WhatsApp adapters
│   └── presentation/       FastAPI routers + webhooks
├── tests/
│   ├── unit/               Sin DB
│   ├── integration/        Con DB real
│   └── e2e/                Stack completo
├── migrations/             Alembic
├── docker-compose.yml      Postgres + Redis + MailHog para dev
├── pyproject.toml
├── Dockerfile
└── .env.example
```

## Comandos comunes

```bash
# Lint + format
uv run ruff check src
uv run ruff format src

# Typecheck
uv run mypy src

# Tests
uv run pytest -q                          # todos
uv run pytest tests/unit -q               # solo unit
uv run pytest -m "not e2e" -q             # excluir e2e

# Migraciones
uv run alembic revision --autogenerate -m "add appointments table"
uv run alembic upgrade head
uv run alembic downgrade -1
```

## Documentación adicional

Ver el repo principal del proyecto para:

- `docs/architecture.md` — Decisiones arquitectónicas en detalle
- `docs/ddd-guide.md` — Cómo agregar features siguiendo DDD
- `docs/api-contract.md` — Contrato API con el frontend
- `docs/roadmap.md` — Fases 1-3 de desarrollo

## Contribuir

Ver [CONTRIBUTING.md](CONTRIBUTING.md).

## Licencia

MIT — ver [LICENSE](LICENSE).
