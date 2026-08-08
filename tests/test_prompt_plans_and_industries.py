"""The plan catalogue in the prompt, and the restaurant industry hint.

Plans used to live only behind get_membership_plans, so an open "¿qué ofrecen?"
was answered from the services already in the prompt and the plans were never
mentioned. They are preloaded now, the same way services are.
"""

from uuid import uuid4

from src.domain.business.business import Business
from src.domain.membership.membership_plan import MembershipPlan
from src.domain.membership.value_objects import BillingPeriod
from src.domain.service.service import Service
from src.domain.shared.channel import Channel
from src.infrastructure.ai.system_prompt import build_system_prompt

TENANT_ID = uuid4()


def _business() -> Business:
    return Business.create(
        tenant_id=TENANT_ID,
        name="Gimnasio",
        slug="gimnasio",
        phone="59171234567",
        timezone="America/La_Paz",
    )


def _service(business: Business) -> Service:
    return Service.create(
        tenant_id=TENANT_ID,
        business_id=business.id,
        name="Clase grupal",
        duration_minutes=60,
        price=0,
        capacity=20,
    )


def _plan(business: Business, name: str, price: int, period: BillingPeriod) -> MembershipPlan:
    return MembershipPlan.create(
        tenant_id=TENANT_ID,
        business_id=business.id,
        name=name,
        price=price,
        billing_period=period,
    )


def _prompt(business: Business, *, plans=None, industry: str = "") -> str:
    return build_system_prompt(
        business=business,
        services=[_service(business)],
        client_name="Ana",
        is_returning_client=False,
        industry=industry,
        channel=Channel.WHATSAPP,
        plans=plans,
    )


# ── The plan catalogue ───────────────────────────────────────────────────────


def test_plans_are_listed_with_price_and_period():
    business = _business()
    plans = [
        _plan(business, "Mensual", 25_000, BillingPeriod.MONTHLY),
        _plan(business, "Anual", 220_000, BillingPeriod.ANNUAL),
    ]

    prompt = _prompt(business, plans=plans)

    assert "PLANES DE MEMBRESÍA" in prompt
    assert "Mensual — $250 al mes" in prompt
    assert "Anual — $2200 al año" in prompt


def test_the_agent_is_told_to_offer_plans_unprompted():
    """The whole point of preloading them: an open question must surface plans."""
    business = _business()

    prompt = _prompt(business, plans=[_plan(business, "Mensual", 25_000, BillingPeriod.MONTHLY)])

    assert "no solo cuando digan" in prompt


def test_a_business_without_plans_renders_nothing():
    business = _business()

    assert "PLANES DE MEMBRESÍA" not in _prompt(business, plans=[])
    assert "PLANES DE MEMBRESÍA" not in _prompt(business, plans=None)


# ── Restaurant hint ──────────────────────────────────────────────────────────


def test_restaurant_hint_asks_how_many_people():
    """Party size decides which service to book — a table for 2 or the long one."""
    prompt = _prompt(_business(), industry="restaurantes")

    assert "PARA CUÁNTAS PERSONAS" in prompt
    assert "bolos" in prompt


def test_hair_salon_hint_asks_which_stylist():
    """Volver con la misma persona es la regla del rubro, y darle otra sin
    avisar es el reclamo más común."""
    prompt = _prompt(_business(), industry="peluqueria")

    assert "CON QUÉ ESTILISTA" in prompt
    # Un corte y un balayage no duran lo mismo: el agente no debe ofrecer un
    # hueco corto para un servicio largo.
    assert "duración real del servicio" in prompt


def test_an_unknown_industry_adds_no_hint():
    prompt = _prompt(_business(), industry="floristeria")

    assert "PARA CUÁNTAS PERSONAS" not in prompt
