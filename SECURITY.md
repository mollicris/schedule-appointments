# Security Policy — Backend

## Reportar una vulnerabilidad

Si descubres una vulnerabilidad de seguridad, **no abras un issue público**. En su lugar:

1. Envía un email a **security@agentecitas.example** (reemplazar con dirección real cuando se configure).
2. Incluye:
   - Descripción del problema
   - Pasos para reproducir
   - Impacto potencial (qué datos podrían comprometerse)
   - Versión afectada (commit hash o tag)

Confirmaremos recepción en 48 horas y trabajaremos contigo para resolver y coordinar la divulgación.

## Versiones soportadas

Por ahora solo `main`. Cuando se etiqueten releases (`v1.0.0+`), se documentarán versiones soportadas aquí.

## Áreas sensibles del código

Cualquier cambio sobre estas áreas requiere revisión adicional de seguridad:

### Aislamiento multi-tenant
- `src/infrastructure/persistence/tenant_session.py` — setea `app.current_tenant_id` por sesión
- Migraciones con políticas RLS (Row-Level Security) de PostgreSQL
- `src/application/shared/tenant_context.py` — `TenantContext` y validación cross-tenant
- **Un bug aquí puede leakear datos entre tenants.**

### Webhooks externos
- `src/presentation/webhooks/router.py` — debe validar HMAC SIEMPRE antes de procesar
- WhatsApp Cloud API: HMAC-SHA256 con app secret del tenant
- Instagram, web widget: cada uno con su esquema de firma

### Autenticación y tokens
- JWT issuance (cuando se implemente)
- Password hashing con Argon2id
- Refresh tokens con rotation
- Verification tokens de email/phone con TTL corto

### PII en logs
- Phone numbers, emails, contenido de mensajes deben redactarse en logs estructurados
- Configurar processors de structlog para mascarar campos sensibles

### Secretos
- Nunca commitear `.env`. Usar `.env.example` con placeholders
- En producción: AWS Secrets Manager / Vault / equivalente
- Rotar `JWT_SECRET_KEY` periódicamente

## Buenas prácticas

- Los webhooks de WhatsApp validan HMAC antes de hacer queries a la DB
- Las queries siempre filtran por `tenant_id`, no solo por `id`
- Los endpoints públicos (`/onboarding/register`, `/onboarding/verify`) tienen rate-limit estricto
- Las imágenes/audios subidos por clientes se validan (tamaño, MIME type) antes de procesarse

## Dependencias

- `uv` con `--frozen` en CI garantiza versiones idénticas en prod
- Auditar dependencias regularmente (cuando GitHub Dependabot esté habilitado)
- Evitar dependencias con < 100 stars o sin maintainer activo
