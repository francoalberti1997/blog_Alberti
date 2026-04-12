from reportlab.platypus import Paragraph, Spacer, PageBreak
from .styles import h1, normal
from reportlab.lib.units import cm
from .material.lcs import build_steel
from .material.magnesia import build_magnesia

MATERIAL_BUILDERS = {
    "Acero de bajo carbono": build_steel,
    "Magnesia": build_magnesia,
}


def fallback_material(material_name: str) -> list:
    return [
        Paragraph("Sección específica del material", h1),
        Spacer(1, 1.5 * cm),
        Paragraph(
            f"No hay template definido para el material: {material_name}",
            normal
        ),
        PageBreak()
    ]


def build_material_specific(data: dict) -> list:
    material_name = data["meta"]["material_name"]

    print(f"Construyendo sección específica para material: {material_name}")
    builder = MATERIAL_BUILDERS.get(material_name)

    if builder:
        return builder(data)

    return fallback_material(material_name)