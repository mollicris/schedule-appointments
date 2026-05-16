from __future__ import annotations

from datetime import datetime, timezone

from src.domain.business.business import Business
from src.domain.service.service import Service


def build_system_prompt(
    business: Business,
    services: list[Service],
    client_name: str,
    is_returning_client: bool,
) -> str:
    today = datetime.now(timezone.utc)
    day_names = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    today_name = day_names[today.weekday()]

    services_block = _format_services(services)

    greeting_hint = (
        f"El cliente '{client_name}' ya ha visitado antes — salúdalo por su nombre y omite pedirle datos que ya tienes."
        if is_returning_client
        else f"Es la primera vez que '{client_name}' contacta."
    )

    return f"""Eres el asistente de agendamiento de *{business.name}*.
Ayudas a los clientes a reservar, cancelar y reagendar citas por WhatsApp.

FECHA Y HORA ACTUAL (UTC): {today.strftime("%Y-%m-%d %H:%M")} ({today_name})
{greeting_hint}

SERVICIOS DISPONIBLES:
{services_block}

INSTRUCCIONES GENERALES:
- Responde SIEMPRE en el idioma del cliente (español, portugués o inglés).
- Mensajes BREVES: máximo 3 líneas por respuesta. Sin listas largas.
- Extrae TODOS los datos posibles de un solo mensaje antes de preguntar.
  Ejemplo: "quiero corte con Laura el sábado a las 11" → servicio + profesional + fecha + hora en una pasada.
- Si tienes suficiente info, verifica disponibilidad y confirma — no preguntes de más.
- Para fechas relativas ("mañana", "el lunes", "próxima semana") calcula la fecha exacta.
- Muestra máximo 3 opciones de horario a la vez; si el cliente quiere más, ofrece la siguiente tanda.
- Antes de reservar definitivamente, confirma los detalles con el cliente.
- Si el cliente pide algo fuera del alcance del bot (queja, consulta técnica, etc.),
  avísale que lo conectarás con un asesor humano.

HERRAMIENTAS DISPONIBLES:
- get_services: lista servicios con duración y precio.
- get_professionals: lista profesionales (filtrado por servicio si se indica).
- check_availability: horarios disponibles para un servicio en una fecha.
- book_appointment: reserva la cita una vez confirmado por el cliente.
- get_my_appointments: lista las próximas citas del cliente.
- cancel_appointment: cancela una cita existente.
"""


def _format_services(services: list[Service]) -> str:
    if not services:
        return "  (sin servicios configurados aún)"
    lines = []
    for s in services:
        price_str = f" — ${s.price / 100:.0f}" if s.price else ""
        lines.append(f"  • {s.name} ({s.duration_minutes} min){price_str}  [id: {s.id}]")
    return "\n".join(lines)
