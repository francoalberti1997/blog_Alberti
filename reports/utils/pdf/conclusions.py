# reports/utils/pdf/components/conclusions.py
from reportlab.platypus import Paragraph, Spacer, KeepTogether
from .styles import h1, normal
from reportlab.lib.units import cm

def build_conclusions(data: dict) -> list:
    elements = []
    text = f"""
    <b>Fecha del reporte:</b> {data['fecha_actual']}<br/><br/>
    <b>Conclusiones del análisis microestructural</b><br/><br/>
    Las conclusiones detalladas correspondientes al material 
    <b>{data['material_name']}</b> y a la muestra <b>{data['muestra_nombre']}</b> 
    se encuentran en la sección específica del material.
    """

    elements.append(Paragraph("5. Conclusiones", h1))
    elements.append(Spacer(1, 1.0*cm))
    elements.append(Paragraph(text, normal))
    elements.append(Spacer(1, 3.0*cm))
    return elements