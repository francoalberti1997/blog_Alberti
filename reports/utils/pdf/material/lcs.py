from reportlab.platypus import PageBreak, Paragraph
from ..styles import h1, normal


def build_steel(data: dict) -> list:
    material = data["material"]
    meta = data["meta"]

    return [
        Paragraph("2. Acero - Resumen", h1),
        Paragraph(f"Tamaño de grano: {material['grain_size']} µm", normal),
        Paragraph(f"Fases: {', '.join(material['phases'])}", normal),
        Paragraph(f"Norma ASTM: {material['astm_standard']}", normal),
        PageBreak()
    ]

def build_steel_data(pdf_obj) -> dict:

    return {
        "grain_size": 12.5,
        "phases": ["ferrite", "pearlite"],
        "astm_standard": "E112"
    }