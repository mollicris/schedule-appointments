# API Response Structure

## Overview

Toda respuesta de la API sigue una estructura consistente con campos estándar para éxito, error, mensajes y datos.

## Respuesta Exitosa (2xx)

### Estructura Base
```json
{
  "success": true,
  "message": "Human-readable success message",
  "code": "RESPONSE_CODE",
  "data": {
    // ... response data ...
  }
}
```

### Ejemplo: Tenant Registration (201 Created)
```json
{
  "success": true,
  "message": "Tenant registered successfully. A verification email has been sent.",
  "code": "TENANT_REGISTERED",
  "data": {
    "tenant_id": "64b1da92-4950-4242-8a02-7d3406b4fdb7",
    "slug": "test-salon-final",
    "verification_sent_to": "admin@finalsalon.io"
  }
}
```

### Ejemplo: List Response (Paginated)
```json
{
  "success": true,
  "message": "Items retrieved successfully",
  "code": "ITEMS_RETRIEVED",
  "data": [
    { "id": "...", "name": "..." },
    { "id": "...", "name": "..." }
  ],
  "pagination": {
    "total": 100,
    "page": 1,
    "page_size": 10,
    "pages": 10
  }
}
```

## Respuesta de Error (4xx, 5xx)

### Estructura Base
```json
{
  "success": false,
  "message": "Human-readable error message",
  "code": "ERROR_CODE",
  "errors": [
    {
      "field": "field_name",
      "code": "ERROR_CODE",
      "message": "Error message"
    }
  ]
}
```

### Ejemplo: Validation Error (422)
```json
{
  "success": false,
  "message": "Validation failed",
  "code": "VALIDATION_ERROR",
  "errors": [
    {
      "field": "admin_password",
      "code": "TOO_SHORT",
      "message": "Password must be at least 8 characters"
    },
    {
      "field": "email",
      "code": "INVALID_EMAIL",
      "message": "Invalid email format"
    }
  ]
}
```

### Ejemplo: Conflict Error (409)
```json
{
  "success": false,
  "message": "An account already exists for example@company.com",
  "code": "CONFLICT",
  "errors": [
    {
      "code": "CONFLICT",
      "message": "An account already exists for example@company.com"
    }
  ]
}
```

### Ejemplo: Not Found (404)
```json
{
  "success": false,
  "message": "Tenant not found",
  "code": "NOT_FOUND",
  "errors": [
    {
      "code": "NOT_FOUND",
      "message": "Tenant with id '...' not found"
    }
  ]
}
```

## HTTP Status Codes

| Código | Significado | Uso |
|--------|-------------|-----|
| 200 | OK | Operación exitosa (GET, updates) |
| 201 | Created | Recurso creado (POST, PUT) |
| 204 | No Content | Sin contenido (DELETE) |
| 400 | Bad Request | Violación de regla de negocio |
| 401 | Unauthorized | Autenticación requerida |
| 403 | Forbidden | Falta de permisos |
| 404 | Not Found | Recurso no encontrado |
| 409 | Conflict | Duplicado/Conflicto de datos |
| 422 | Unprocessable Entity | Error de validación |
| 500 | Internal Server Error | Error inesperado |

## Response Codes

Códigos estándar para cada operación:

| Código | Significado |
|--------|-------------|
| `TENANT_REGISTERED` | Tenant registrado exitosamente |
| `TENANT_VERIFIED` | Email verificado |
| `VALIDATION_ERROR` | Error en validación de datos |
| `CONFLICT` | Conflicto de datos (duplicado) |
| `NOT_FOUND` | Recurso no encontrado |
| `FORBIDDEN` | Falta de permisos |
| `UNAUTHORIZED` | Autenticación requerida |
| `BUSINESS_RULE_VIOLATION` | Violación de regla de negocio |
| `INTERNAL_ERROR` | Error interno del servidor |

## Helpers de Respuesta

Para construir respuestas consistentes, usa los helpers en `src/presentation/schemas/helpers.py`:

### Success Response
```python
from src.presentation.schemas import success_response

return success_response(
    data=tenant_data,
    message="Tenant created successfully",
    code="TENANT_CREATED"
)
```

### Paginated Response
```python
from src.presentation.schemas import paginated_response

return paginated_response(
    items=tenants,
    total=100,
    page=1,
    page_size=10,
    message="Tenants retrieved successfully",
    code="TENANTS_RETRIEVED"
)
```

## Exception Handling

Los errores del dominio se convierten automáticamente a respuestas HTTP apropiadas:

```python
from src.domain.shared.errors import ConflictError, ValidationError

# Estos errores se convierten automáticamente:
raise ConflictError("Email already registered")  # → 409 Conflict
raise ValidationError("Password too short")      # → 422 Unprocessable Entity
raise NotFoundError("Tenant not found")          # → 404 Not Found
```

Los exception handlers en `src/presentation/exception_handlers.py` se encargan de la conversión.

## Documentación en Swagger

Accede a la documentación interactiva en:
- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`

Todas las respuestas están documentadas automáticamente según los `response_model` definidos.
