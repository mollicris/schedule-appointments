from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceTemplate:
    name: str
    description: str
    duration_minutes: int


_TEMPLATES: dict[str, list[ServiceTemplate]] = {
    "salones-y-peluquerias": [
        ServiceTemplate("Corte de cabello", "Corte básico para dama o caballero", 30),
        ServiceTemplate("Coloración", "Tinte completo con productos profesionales", 90),
        ServiceTemplate("Tratamiento capilar", "Hidratación o keratina", 60),
        ServiceTemplate("Manicure", "Limpieza y esmaltado de uñas", 45),
        ServiceTemplate("Pedicure", "Cuidado completo de pies", 45),
    ],
    "veterinarias": [
        ServiceTemplate("Consulta general", "Revisión clínica completa", 30),
        ServiceTemplate("Vacunación", "Aplicación de vacuna según esquema", 15),
        ServiceTemplate("Baño y peluquería", "Baño, secado y corte de pelo", 60),
        ServiceTemplate("Cirugía programada", "Procedimiento quirúrgico electivo", 120),
    ],
    "mecanicos": [
        ServiceTemplate("Cambio de aceite", "Cambio de aceite y filtro", 30),
        ServiceTemplate("Diagnóstico general", "Revisión completa del vehículo", 45),
        ServiceTemplate("Alineación y balanceo", "Alineación de dirección y balanceo de ruedas", 60),
        ServiceTemplate("Servicio de frenos", "Revisión y cambio de pastillas o discos", 90),
        ServiceTemplate("Mantenimiento preventivo", "Revisión completa según kilometraje", 120),
    ],
    "clinicas": [
        ServiceTemplate("Consulta médica", "Consulta con médico general o especialista", 30),
        ServiceTemplate("Consulta de seguimiento", "Control de tratamiento o evolución", 20),
        ServiceTemplate("Revisión preventiva", "Chequeo anual de salud", 45),
        ServiceTemplate("Procedimiento menor", "Intervención ambulatoria simple", 60),
    ],
    "gimnasios": [
        ServiceTemplate("Clase grupal", "Clase colectiva de fitness o baile", 60),
        ServiceTemplate("Sesión personal", "Entrenamiento one-to-one con instructor", 60),
        ServiceTemplate("Evaluación física", "Medición de composición corporal y fitness", 45),
        ServiceTemplate("Yoga", "Clase de yoga o meditación guiada", 60),
    ],
}

_DEFAULT: list[ServiceTemplate] = [
    ServiceTemplate("Consulta / Servicio", "Servicio principal del negocio", 30),
]


def get_templates(industry: str) -> list[ServiceTemplate]:
    """Return default service templates for the given industry slug."""
    return _TEMPLATES.get(industry, _DEFAULT)
