# reports/utils/pdf/components/conclusions.py
from reportlab.platypus import Paragraph, Spacer
from .styles import h1, normal
from reportlab.lib.units import cm


def build_conclusions(data: dict) -> list:
    elements = []

    # ================================================
    # Texto genérico de conclusiones
    # ================================================
    text = f"""
    <b>Fecha del reporte:</b> {data['fecha_actual']}<br/><br/>
    <b>Conclusiones del análisis microestructural</b><br/><br/>
    Se ha presentado un análisis microestructural correspondiente al material 
    <b>{data['material_name']}</b> y a la muestra <b>{data['muestra_nombre']}</b>.
    """

    elements.append(Paragraph("5. Conclusiones", h1))
    elements.append(Spacer(1, 1.0 * cm))
    elements.append(Paragraph(text, normal))
    elements.append(Spacer(1, 2.0 * cm))
    return elements