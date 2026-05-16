from __future__ import annotations

import re
from datetime import date, time, timedelta

# ── Day / month name maps ─────────────────────────────────────────────────────

_DAYS: dict[str, int] = {
    "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2,
    "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6,
    # Portuguese
    "segunda": 0, "terça": 1, "terca": 1, "quarta": 2,
    "quinta": 3, "sexta": 4, "sábado": 5, "domingo": 6,
}

_MONTHS: dict[str, int] = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    # Portuguese
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}


def parse_date(text: str, today: date) -> date | None:
    """Parse natural-language date expressions in Spanish/Portuguese.

    Returns a date object or None if unrecognised.
    """
    t = text.lower().strip()

    # ── ISO format ───────────────────────────────────────────────────────────
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # DD/MM/YYYY or DD-MM-YYYY
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", t)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))

    # ── Relative keywords ────────────────────────────────────────────────────
    if re.search(r"\bpasado\s+ma[ñn]ana\b", t):
        return today + timedelta(days=2)
    if re.search(r"\bma[ñn]ana\b", t):
        return today + timedelta(days=1)
    if re.search(r"\bhoy\b|\bogden\b", t):
        return today

    # ── Named weekday (próximo lunes / el lunes) ─────────────────────────────
    force_next = bool(re.search(r"\bpr[oó]ximo\b|\bpróxima\b|\bque viene\b", t))
    for day_name, day_num in _DAYS.items():
        if re.search(rf"\b{re.escape(day_name)}\b", t):
            delta = (day_num - today.weekday()) % 7
            if delta == 0 or force_next:
                delta += 7
            return today + timedelta(days=delta)

    # ── Day + optional month ("el 5 de junio", "el 15", "el 5/6") ───────────
    m = re.search(r"\bel\s+(\d{1,2})(?:\s+de\s+([a-záéíóúñ]+))?", t)
    if m:
        day_n = int(m.group(1))
        month_name = m.group(2)
        if month_name and month_name in _MONTHS:
            month_n = _MONTHS[month_name]
            year = today.year if (month_n, day_n) >= (today.month, today.day) else today.year + 1
        else:
            month_n = today.month
            if day_n < today.day:
                month_n = today.month + 1
                if month_n > 12:
                    month_n = 1
            year = today.year
        try:
            return date(year, month_n, day_n)
        except ValueError:
            pass

    # ── Bare day number with month keyword ("5 de junio") ───────────────────
    m = re.search(r"\b(\d{1,2})\s+de\s+([a-záéíóúñ]+)", t)
    if m and m.group(2) in _MONTHS:
        day_n = int(m.group(1))
        month_n = _MONTHS[m.group(2)]
        year = today.year if (month_n, day_n) >= (today.month, today.day) else today.year + 1
        try:
            return date(year, month_n, day_n)
        except ValueError:
            pass

    return None


def parse_time(text: str) -> time | None:
    """Parse natural-language time expressions in Spanish/Portuguese.

    Returns a time object or None if unrecognised.
    """
    t = text.lower().strip()

    # HH:MM (24h or 12h)
    m = re.search(r"\b(\d{1,2}):(\d{2})\b", t)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if "pm" in t and h < 12:
            h += 12
        if "am" in t and h == 12:
            h = 0
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return time(h, mi)

    # X am/pm
    m = re.search(r"\b(\d{1,2})\s*(am|pm)\b", t)
    if m:
        h = int(m.group(1))
        if m.group(2) == "pm" and h < 12:
            h += 12
        if m.group(2) == "am" and h == 12:
            h = 0
        if 0 <= h <= 23:
            return time(h, 0)

    # "a las X" / "las X" / "a las X de la mañana/tarde"
    m = re.search(r"(?:a\s+las?|las?)\s*(\d{1,2})(?::(\d{2}))?", t)
    if m:
        h = int(m.group(1))
        mi = int(m.group(2)) if m.group(2) else 0
        # Infer am/pm from context words
        if re.search(r"\btarde\b|\bnoche\b", t) and h < 12:
            h += 12
        elif re.search(r"\bma[ñn]ana\b", t) and h > 12:
            h -= 12
        elif h < 7:
            # Ambiguous single-digit hour: assume afternoon
            h += 12
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return time(h, mi)

    # Bare hour number after "noon" keywords
    m = re.search(r"\b(\d{1,2})\s+(?:horas?|h)\b", t)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            return time(h, 0)

    return None
