from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.application.membership.get_client_membership import GetClientMembershipOutput
from src.domain.business.business import Business
from src.domain.service.service import Service
from src.domain.shared.channel import Channel

# Industry-specific instructions injected into the system prompt.
# Keys match the Tenant.industry values set during registration.
_INDUSTRY_HINTS: dict[str, str] = {
    "veterinarias": (
        "DATOS ADICIONALES PARA ESTE NEGOCIO (veterinaria):\n"
        "Al reservar una cita SIEMPRE recopila, antes de confirmar:\n"
        "  1. Nombre de la mascota\n"
        "  2. Especie (perro, gato, conejo, etc.)\n"
        "  3. Motivo de la consulta o problema\n"
        "Incluye el nombre de la mascota en el resumen de confirmación."
    ),
    "salones-y-peluquerias": (
        "DATOS ADICIONALES PARA ESTE NEGOCIO (salón / peluquería):\n"
        "Al reservar, ofrece al cliente la opción de indicar preferencias de estilo "
        "(largo, color, referencias). No es obligatorio; si no comenta nada, confirma la cita sin preguntar de nuevo."
    ),
    "mecanicos": (
        "DATOS ADICIONALES PARA ESTE NEGOCIO (taller mecánico):\n"
        "Al reservar una cita SIEMPRE recopila, antes de confirmar:\n"
        "  1. Marca y modelo del vehículo (ej: Toyota Corolla 2019)\n"
        "  2. Descripción breve del problema o servicio requerido\n"
        "Incluye el vehículo en el resumen de confirmación."
    ),
    "clinicas": (
        "DATOS ADICIONALES PARA ESTE NEGOCIO (clínica / salud):\n"
        "Al reservar, pregunta:\n"
        "  1. Motivo principal de la consulta o síntoma\n"
        "  2. Si es primera consulta o seguimiento\n"
        "Sé discreto y empático con el tema de salud."
    ),
    "gimnasios": (
        "DATOS ADICIONALES PARA ESTE NEGOCIO (gimnasio / entrenamiento):\n"
        "Si el servicio es una sesión personalizada, pregunta brevemente el objetivo "
        "(pérdida de peso, tonificación, rehabilitación, etc.). "
        "Para clases grupales no es necesario.\n"
        "Las clases grupales tienen cupos limitados: al ofrecer horarios, menciona los "
        "cupos que quedan solo si son 3 o menos ('quedan 2 cupos').\n"
        "Si preguntan por planes o precios de membresía, usa get_membership_plans y "
        "menciona máximo 3 planes.\n"
        "Si la membresía del cliente está vencida o congelada: avísale en UNA línea, "
        "ofrécele renovar en recepción y CONFIRMA LA RESERVA IGUAL. No la bloquees ni "
        "repitas el aviso en mensajes siguientes.\n"
        "Si quiere comprar, renovar o pagar un plan: usa notify_staff (avisa a recepción) "
        "y SIGUE atendiéndolo con normalidad — puede reservar clases en el mismo chat. "
        "No uses transfer_to_human para ventas: eso te deja mudo."
    ),
}


def build_system_prompt(
    business: Business,
    services: list[Service],
    client_name: str,
    is_returning_client: bool,
    industry: str = "",
    membership: GetClientMembershipOutput | None = None,
    channel: Channel = Channel.WHATSAPP,
) -> str:
    # Everything the client hears must be in the business's local time: a gym in
    # La Paz says "a las 10" meaning 10:00 local, not 10:00 UTC.
    try:
        tz = ZoneInfo(business.timezone or "UTC")
    except ZoneInfoNotFoundError:
        tz = timezone.utc
    today = datetime.now(tz)
    day_names = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    today_name = day_names[today.weekday()]

    services_block = _format_services(services)

    greeting_hint = (
        f"El cliente '{client_name}' ya ha visitado antes — salúdalo por su nombre y omite pedirle datos que ya tienes."
        if is_returning_client
        else f"Es la primera vez que '{client_name}' contacta."
    )

    industry_block = ""
    if industry:
        hint = _INDUSTRY_HINTS.get(industry.lower())
        if hint:
            industry_block = f"\n{hint}\n"

    membership_block = _format_membership(membership)
    channel_block = _format_channel(channel, business)

    return f"""Eres el asistente de agendamiento de *{business.name}*.
Ayudas a los clientes a reservar, cancelar y reagendar citas por WhatsApp.

FECHA Y HORA ACTUAL: {today.strftime("%Y-%m-%d %H:%M")} ({today_name}) — hora local de {business.timezone or "UTC"}
{greeting_hint}

SERVICIOS DISPONIBLES:
{services_block}
{membership_block}{channel_block}{industry_block}
INSTRUCCIONES GENERALES:
- Responde SIEMPRE en el idioma del cliente (español, portugués o inglés).
- Mensajes BREVES: máximo 3 líneas por respuesta. Sin listas largas.
- HORAS: habla SIEMPRE en hora local. Cuando el cliente dice "a las 10" se refiere
  a las 10:00 locales. Las herramientas devuelven cada horario con dos campos:
  usa `hora_local` para escribirle al cliente y `inicio_utc` tal cual, sin
  recalcularlo, cuando llames a book_appointment o reschedule_appointment.
- Extrae TODOS los datos posibles de un solo mensaje antes de preguntar.
  Ejemplo: "quiero corte con Laura el sábado a las 11" → servicio + profesional + fecha + hora en una pasada.
- Si tienes suficiente info, verifica disponibilidad y confirma — no preguntes de más.
- Para fechas relativas ("mañana", "el lunes", "próxima semana") calcula la fecha exacta.
- Muestra máximo 3 opciones de horario a la vez; si el cliente quiere más, ofrece la siguiente tanda.
- Antes de reservar definitivamente, confirma los detalles con el cliente.
- Si el cliente pide hablar con una persona, hace una queja, o solicita algo fuera de
  tu alcance: llama a transfer_to_human(reason="...") con la razón, luego avísale
  que lo conectarás con un asesor humano. NO intentes resolver esa solicitud tú mismo.
  Eso te deja MUDO hasta que un humano intervenga, así que úsalo solo en esos casos.
- Si solo hace falta que recepción haga un seguimiento (quiere comprar o renovar un
  plan, pedir factura, pagar): usa notify_staff(reason="...") y CONTINÚA la
  conversación con normalidad.

HERRAMIENTAS DISPONIBLES:
- get_services: lista servicios con duración y precio.
- get_professionals: lista profesionales (filtrado por servicio si se indica).
- check_availability: horarios disponibles para un servicio en una fecha.
- book_appointment: reserva la cita una vez confirmado por el cliente.
- get_my_appointments: lista las próximas citas del cliente.
- cancel_appointment: cancela una cita existente.
- reschedule_appointment: mueve una cita existente a otra fecha y hora.
- get_membership_plans: planes de membresía con precio y período.
- get_my_membership: estado de la membresía del cliente (vigencia y días restantes).
- notify_staff: avisa a recepción sin cortar la conversación (ventas, cobros, facturas).
- transfer_to_human: escala la conversación a un asesor humano.
"""


def _format_services(services: list[Service]) -> str:
    if not services:
        return "  (sin servicios configurados aún)"
    lines = []
    for s in services:
        price_str = f" — ${s.price / 100:.0f}" if s.price else ""
        # Only group classes mention capacity; one-to-one services stay as before.
        capacity_str = f" — clase grupal, {s.capacity} cupos" if s.is_group_class else ""
        lines.append(
            f"  • {s.name} ({s.duration_minutes} min){price_str}{capacity_str}  [id: {s.id}]"
        )
    return "\n".join(lines)


def _format_channel(channel: Channel, business: Business) -> str:
    """Rules that only apply on Facebook and Instagram.

    On those inboxes we cannot verify who is writing — the account may be shared
    and the id tells us nothing — so the bot informs and captures the contact
    instead of booking. WhatsApp keeps the full flow and gets no extra block.
    """
    if not channel.is_social:
        return ""

    contacto = f" o al WhatsApp {business.phone}" if business.phone else ""
    return (
        f"\nCANAL: {channel.label_es}. Aquí NO puedes reservar, cancelar ni reagendar, "
        "y no tienes acceso al historial ni a la membresía de quien escribe.\n"
        "Sí puedes informar servicios, precios, planes y horarios disponibles.\n"
        "Si quiere reservar: pídele nombre y teléfono, llama a capture_lead y confírmale "
        f"que recepción lo contactará{contacto}.\n"
        "Nunca digas que la reserva quedó confirmada.\n"
    )


def _format_membership(membership: GetClientMembershipOutput | None) -> str:
    """Two-line block with the client's membership, or nothing when not applicable.

    Kept short on purpose: the prompt caps replies at 3 lines, so the agent must
    not have to summarise a long block.
    """
    if membership is None:
        return ""

    if not membership.has_membership:
        return "\nMEMBRESÍA DEL CLIENTE: no tiene membresía registrada.\n"

    plan = membership.plan_name or "plan sin nombre"
    ends = membership.ends_at.strftime("%d/%m/%Y") if membership.ends_at else "sin fecha"

    if membership.is_current:
        return (
            f"\nMEMBRESÍA DEL CLIENTE: {plan} — vigente hasta {ends} "
            f"({membership.days_remaining} días).\n"
        )

    return (
        f"\nMEMBRESÍA DEL CLIENTE: {plan} — NO vigente. {membership.warning or ''}\n"
        "Avísale una vez, ofrece renovar en recepción y reserva igual.\n"
    )
