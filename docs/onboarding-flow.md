# Tenant Onboarding Flow

## Overview

El flujo de onboarding de un nuevo tenant tiene tres fases:

1. **Registration (PENDING_VERIFICATION)** - El admin se registra
2. **Email Verification (ONBOARDING)** - El admin verifica su email
3. **Setup Wizard (ACTIVE)** - El admin completa la configuración (próxima fase)

## Phase 1: Registration

### Endpoint
```
POST /api/v1/onboarding/register
Content-Type: application/json

{
  "name": "Mi Salón de Belleza",
  "admin_email": "admin@salon.io",
  "admin_password": "SecurePassword123!",
  "industry": "hair_salon",
  "desired_slug": null
}
```

### Response (201 Created)
```json
{
  "success": true,
  "message": "Tenant registered successfully. A verification email has been sent.",
  "code": "TENANT_REGISTERED",
  "data": {
    "tenant_id": "64b1da92-4950-4242-8a02-7d3406b4fdb7",
    "slug": "mi-salon-de-belleza",
    "verification_sent_to": "admin@salon.io"
  }
}
```

### What Happens

1. ✅ Tenant es creado con status `PENDING_VERIFICATION`
2. ✅ Admin user es creado con role `admin` (la contraseña se hashea con Argon2)
3. ✅ Token de verificación se genera (válido por 24 horas)
4. ✅ Email se envía al admin (en producción, con SendGrid o similar)
5. ✅ Tenant tiene acceso de lectura a su propio tenant (RLS)

### Validations

| Campo | Rules | Error |
|-------|-------|-------|
| `name` | 2-120 chars, no vacío | `VALIDATION_ERROR` (422) |
| `admin_email` | Email válido, no existe | `CONFLICT` (409) si ya existe |
| `admin_password` | 8-128 chars | `VALIDATION_ERROR` (422) |
| `industry` | 2-40 chars, requerido | `VALIDATION_ERROR` (422) |
| `desired_slug` | 0-48 chars, único, opcional | Auto-generado si no se proporciona |

### Slug Generation

Si no se proporciona `desired_slug`:
- Se genera automáticamente del `name` (slugify: lowercase, guiones, sin espacios)
- Ej: "Mi Salón de Belleza" → "mi-salon-de-belleza"
- Si ya existe, se agrega número: "mi-salon-de-belleza-2"
- Máximo 48 caracteres

## Phase 2: Email Verification

### Endpoint
```
POST /api/v1/onboarding/verify/{token}
```

Donde `{token}` es el token recibido en el email.

### Response (200 OK)
```json
{
  "success": true,
  "message": "Email verified successfully. You can now proceed with onboarding.",
  "code": "EMAIL_VERIFIED",
  "data": {
    "tenant_id": "64b1da92-4950-4242-8a02-7d3406b4fdb7",
    "slug": "mi-salon-de-belleza",
    "admin_email": "admin@salon.io"
  }
}
```

### What Happens

1. ✅ Token es validado (debe existir y no estar expirado)
2. ✅ Tenant status cambia: `PENDING_VERIFICATION` → `ONBOARDING`
3. ✅ Tenant puede ahora acceder al setup wizard
4. ✅ Email está confirmado (usado para password reset, notificaciones, etc)

### Error Scenarios

#### Invalid Token (422 Unprocessable Entity)
```json
{
  "success": false,
  "message": "Invalid or expired verification token",
  "code": "VALIDATION_ERROR",
  "errors": [
    {
      "code": "VALIDATION_ERROR",
      "message": "Invalid or expired verification token"
    }
  ]
}
```

**Causas:**
- Token no existe
- Token expiró (>24 horas)
- Token fue consumido dos veces (one-time use)

## Phase 3: Setup Wizard (Next Phase)

El admin accede al wizard después de verificar su email:
- Crear business principal
- Configurar servicios
- Agregar profesionales
- Horarios de atención
- Campos personalizados (ej: nombre mascota para vets)

Endpoints del wizard: `/api/v1/wizard/*` (implementación en Progress)

## Complete Flow - Example

### Step 1: User signs up
```bash
curl -X POST http://localhost:9000/api/v1/onboarding/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Salón Luna",
    "admin_email": "maria@salon-luna.io",
    "admin_password": "MiPassword1234!",
    "industry": "hair_salon"
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Tenant registered successfully. A verification email has been sent.",
  "code": "TENANT_REGISTERED",
  "data": {
    "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
    "slug": "salon-luna",
    "verification_sent_to": "maria@salon-luna.io"
  }
}
```

### Step 2: User receives email with token

Email body (template):
```
¡Bienvenida a AgenteCitas!

Para completar tu registro, haz clic en el siguiente enlace:

https://app.agentecitas.io/verify/abc123def456...

Este enlace expira en 24 horas.

¿Preguntas? Contacta a support@agentecitas.io
```

### Step 3: User clicks verification link

Application handles:
```bash
curl -X POST http://localhost:9000/api/v1/onboarding/verify/abc123def456... \
  -H "Content-Type: application/json"
```

**Response:**
```json
{
  "success": true,
  "message": "Email verified successfully. You can now proceed with onboarding.",
  "code": "EMAIL_VERIFIED",
  "data": {
    "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
    "slug": "salon-luna",
    "admin_email": "maria@salon-luna.io"
  }
}
```

### Step 4: Redirect to setup wizard
Application redirects to `/wizard/1` to start business setup.

## Security Considerations

### Password Hashing
- Algoritmo: **Argon2id** (OWASP recomendado)
- Parámetros: m=65536 (65MB), t=3 (3 iteraciones), p=4 (4 paralelismo)
- Nunca se almacenan ni transmiten contraseñas en texto plano

### Token Security
- **Longitud**: 32 caracteres aleatorios (URL-safe)
- **Expiración**: 24 horas
- **One-time use**: Se consume después de verificar
- **Storage**: En desarrollo se usa in-memory (para producción: Redis)

### Email Verification
- **Confirmación requerida**: Email debe ser verificado antes de acceder a wizard
- **Re-envío**: El admin puede solicitar un nuevo token si el anterior expiró
- **Fallback**: Si no recibe email, contactar con support

### Multi-tenancy
- RLS activo: Los usuarios solo ven datos de su tenant
- Tenant ID en JWT: Validado en cada request
- Aislamiento: Las queries de negocio filtran por tenant_id

## Testing

### Unit Tests
```bash
uv run pytest tests/test_verify_email.py -v
```

### Integration Tests
```bash
# Start server
uv run uvicorn src.main:app --port 9000

# Run flow test
uv run python test_onboarding_flow.py
```

### Manual Testing
```bash
# 1. Register
TOKEN=$(curl -X POST http://localhost:9000/api/v1/onboarding/register \
  -H "Content-Type: application/json" \
  -d '...' | jq -r '.data.verification_sent_to')

# 2. Verify (get token from in-memory service)
curl -X POST http://localhost:9000/api/v1/onboarding/verify/your-token

# 3. Check tenant status in DB
psql agent_appointments -c "SELECT id, admin_email, status FROM tenants;"
```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| Email already exists (409) | Email ya registrado | Usar otro email o login |
| Password too short (422) | <8 caracteres | Usar password con 8+ caracteres |
| Invalid token (422) | Token incorrecto/expirado | Solicitar nuevo email |
| Tenant not found (422) | Token apunta a tenant no existente | Contactar support |

## Next Steps (Phase 1 Continuation)

- [ ] Wizard Step 1: Create Business
- [ ] Wizard Steps 2-8: Services, Professionals, Hours, etc.
- [ ] WhatsApp Webhook Integration
- [ ] LangGraph State Machine for Bot
- [ ] Entity Extraction with Claude
