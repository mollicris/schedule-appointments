# Contributing — Backend

Gracias por colaborar en el backend del Agente Citas. Este documento describe el setup local y las convenciones del proyecto.

## Stack

- Python 3.12+
- FastAPI + Pydantic v2
- SQLAlchemy 2.0 async + PostgreSQL 16 + pgvector
- Alembic, Redis, arq, Anthropic SDK, LangGraph
- Gestor de paquetes: **uv**

## Setup local

```bash
# Requisitos: Python 3.12, uv, Docker
pip install uv

# 1. Servicios (Postgres + Redis + MailHog)
docker-compose up -d

# 2. Dependencias
uv sync

# 3. Configurar entorno
cp .env.example .env
# Editar .env con tus credenciales (Anthropic, WhatsApp, etc.)

# 4. Migraciones (cuando existan)
uv run alembic upgrade head

# 5. Levantar la API
uv run uvicorn src.main:app --reload --port 8000
```

API en `http://localhost:8000`. Docs interactivas en `/docs`.

## Arquitectura — DDD + SOLID

El backend sigue **Domain-Driven Design táctico** con 4 capas concéntricas:

```
src/
├── domain/         Núcleo puro — entidades, value objects, eventos. SIN deps externas.
├── application/    Use cases (orquestación). Recibe puertos por DI.
├── infrastructure/ Adapters: SQLAlchemy, Claude, WhatsApp, Redis.
└── presentation/   FastAPI routers, webhooks, schemas Pydantic.
```

**Reglas inviolables**:

- `domain/` NO importa de `fastapi`, `sqlalchemy`, `anthropic`, ni nada externo
- Use cases reciben dependencias por constructor (no singletons globales)
- Repositorios son interfaces (puertos) en `domain/`, implementaciones en `infrastructure/`
- Cada bounded context tiene su propia carpeta (tenant, business, appointment, client, conversation, onboarding, identity)
- Multitenancy: toda entidad excepto `Tenant` extiende `TenantAwareEntity` y tiene `tenant_id`. Postgres RLS lo refuerza a nivel DB.

Ver guía completa en [docs/ddd-guide.md](docs/ddd-guide.md) del proyecto raíz.

## Convenciones

- **Lint/format**: `ruff` (sustituye black + flake8 + isort)
- **Typecheck**: `mypy --strict`
- **Tests**: `pytest`, marcadores `unit` / `integration` / `e2e`
- **Naming**: snake_case en Python, kebab-case en URLs, PascalCase en clases
- **Commits**: imperativo, opcionalmente con scope `feat(appointment): ...`

## Flow de PR

```bash
# Antes de hacer push
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -q
```

1. Rama desde `main`: `feat/<descripcion>`, `fix/<descripcion>`, etc.
2. PR pequeños y enfocados — un PR = un cambio coherente
3. CI debe pasar (`.github/workflows/ci.yml`)
4. Code review obligatorio antes de merge
5. Squash merge a `main`

## Checklist al hacer code review

- [ ] La feature está en el bounded context correcto
- [ ] El dominio no importa nada de `infrastructure/`
- [ ] Cada caso de uso hace UNA cosa
- [ ] Eventos de dominio definidos antes que la lógica que los emite
- [ ] Tests unitarios del dominio sin mocks de DB
- [ ] Repository nuevo respeta `tenant_id` (incluso si RLS lo cubre)
- [ ] Errores son subclases de `DomainError`
- [ ] `mypy --strict` sin nuevos `# type: ignore`

## Reportar bugs

Issues en GitHub con: pasos para reproducir, traceback completo, versión del backend. Vulnerabilidades: ver [SECURITY.md](SECURITY.md).
