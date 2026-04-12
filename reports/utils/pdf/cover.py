# reports/utils/pdf/components/cover.py
import os
import tempfile
import requests
from reportlab.platypus import Paragraph, Spacer, PageBreak
from .styles import title_style, h1, normal
from .template_pdf import image_keep_aspect   # ← tu función existente
from reportlab.lib.units import cm


def build_cover(data: dict) -> list:
    elements = []
    logo_url = data.get("logo_url")

    # Logo
    logo_path = None
    try:
        if logo_url and logo_url.startswith("http"):
            resp = requests.get(logo_url, timeout=10)
            resp.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(resp.content)
                logo_path = f.name

        if logo_path and os.path.exists(logo_path):
            logo_img = image_keep_aspect(logo_path, 9.5, 5.2)
            logo_img.hAlign = 'CENTER'
            elements.append(logo_img)
            elements.append(Spacer(1, 1.6*cm))
        else:
            elements.append(Spacer(1, 2*cm))
    except:
        elements.append(Spacer(1, 2*cm))

    elements.append(Paragraph("Análisis Microestructural", title_style))
    elements.append(Spacer(1, 1.1*cm))
    elements.append(Paragraph(f"Material: <b>{data['material_name']}</b>", h1))
    elements.append(Paragraph(f"Muestra: <b>{data['muestra_nombre']}</b>", h1))
    elements.append(Spacer(1, 2.0*cm))
    elements.append(Paragraph(f"<b>Fecha:</b> {data['fecha_actual']}", normal))
    elements.append(Paragraph(f"<b>Operador:</b> {data['operador_nombre']}", normal))
    elements.append(Paragraph(f"<b>Institución:</b> {data['institucion'] or '—'}", normal))
    elements.append(PageBreak())

    return elements