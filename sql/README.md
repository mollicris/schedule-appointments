# Scripts SQL para Supabase

Scripts para levantar el esquema en Supabase (o cualquier Postgres) sin depender
de correr Alembic desde la máquina. Los dos primeros están **generados** con
`alembic upgrade --sql`, así que son exactamente el mismo DDL que aplica el
backend, incluida la tabla `alembic_version`: después de correrlos,
`alembic upgrade head` no reintenta nada.

| script | cuándo usarlo |
|---|---|
| `001_schema_completo.sql` | Base **vacía**. Crea todo desde cero: 17 tablas, índices, RLS y `alembic_version` en `010`. |
| `002_upgrade_007_a_010.sql` | Base que ya tenía el backend hasta la revisión `007`. Agrega `services.capacity`, las 3 tablas de membresías y `campaign_sends`. |
| `003_seed_gimnasio.sql` | Datos del módulo gimnasios: 3 planes de membresía y los cupos de Yoga / Clase grupal. Idempotente. |
| `004_rls_tolerante_opcional.sql` | Solo si vas a consultar con roles que no son el dueño de las tablas (la API de Supabase con `anon`/`authenticated`). |

Corré **001 o 002**, nunca los dos.

## Cómo correrlos

En el SQL Editor de Supabase, pegá el contenido y ejecutá. O desde tu máquina:

```powershell
$env:PGPASSWORD = "<password del proyecto>"
psql -h db.<ref>.supabase.co -U postgres -d postgres -v ON_ERROR_STOP=1 -f sql/001_schema_completo.sql
psql -h db.<ref>.supabase.co -U postgres -d postgres -v ON_ERROR_STOP=1 -f sql/003_seed_gimnasio.sql
```

Cada script está envuelto en `BEGIN; … COMMIT;`, así que si algo falla no queda
a medias.

## Orden real de puesta en marcha

1. **Extensión pgvector.** El script hace `CREATE EXTENSION IF NOT EXISTS vector`.
   Si el rol no tiene permiso, habilitala antes desde Database → Extensions →
   `vector` y volvé a correr.
2. **Esquema**: `001` o `002`.
3. **Tenant y negocio**: se crean **desde la app**, no por SQL — `POST /api/v1/onboarding/register`,
   verificar el email y completar el wizard. El wizard siembra los servicios de
   la industria y los horarios.
4. **Datos del gimnasio**: `003_seed_gimnasio.sql` (necesita que el negocio ya
   exista; si no lo encuentra avisa y no hace nada).

## Trampas de Supabase que te van a morder

**Pooler y asyncpg.** Supabase da dos cadenas: la directa (puerto **5432**) y la
del pooler PgBouncer (**6543**, modo transaction). El backend usa `asyncpg`, que
depende de prepared statements, y PgBouncer en transaction mode los rompe
(`DuplicatePreparedStatementError`). Usá la directa:

```
DATABASE_URL=postgresql+asyncpg://postgres:<password>@db.<ref>.supabase.co:5432/postgres
```

Si necesitás el pooler, hay que pasar `statement_cache_size=0` al crear el engine
en `src/infrastructure/persistence/database.py` — hoy no está.

**Password con caracteres especiales.** Va URL-encodeado en `DATABASE_URL`. Y ojo
con el `%`: `alembic.ini` lo interpreta como interpolación de configparser (por eso
existe el `.replace("%", "%%")` en `migrations/env.py`).

**RLS.** Las políticas quedan creadas pero **inertes** para el rol dueño de las
tablas, que es el que usa el backend — Postgres omite RLS para el owner. El
aislamiento efectivo lo hace cada repositorio con `WHERE tenant_id = ...`. Si vas
a exponer las tablas por la API de Supabase, corré `004` primero: si no, cualquier
consulta con `anon`/`authenticated` falla porque `app.current_tenant_id` no está
definida en la sesión.

**Zona horaria.** Las columnas son `timestamptz` y el backend escribe algunos
valores con `datetime.utcnow()` (naive), lo que produce un corrimiento igual al
offset del servidor. Supabase corre en **UTC**, así que ahí el corrimiento
desaparece — es decir, los datos nuevos quedan bien, pero cualquier fila migrada
desde tu Postgres local (con offset −04) queda desplazada 4 horas.

## Qué NO incluyen estos scripts

- Datos de tenants, usuarios, clientes, citas o conversaciones: eso es data de
  operación. Si querés migrar tu base local, usá `pg_dump --data-only` sobre las
  tablas que te interesen y revisá antes el punto de zona horaria.
- Secretos: `WHATSAPP_ACCESS_TOKEN`, `ANTHROPIC_API_KEY`, `JWT_SECRET_KEY`,
  `META_APP_*` van en variables de entorno del servicio, nunca en la base.
