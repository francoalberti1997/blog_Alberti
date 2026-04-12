# reports/utils/pdf/components/toc.py
from reportlab.platypus import Paragraph, Spacer, PageBreak
from .styles import h1, normal
from reportlab.lib.units import cm

def build_toc() -> list:
    elements = []
    elements.append(Paragraph("Índice", h1))
    elements.append(Spacer(1, 1.2*cm))

    items = [
        "1. Información de la muestra",
        "2. Resumen general",
        "3. Normas ASTM",
        "4. Máscaras predichas",
        "5. Conclusiones"
    ]

    for item in items:
        elements.append(Paragraph(f"• {item}", normal))
        elements.append(Spacer(1, 0.5*cm))

    elements.append(Spacer(1, 2.0*cm))
    elements.append(PageBreak())
    return elements