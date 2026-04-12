# reports/utils/pdf/components/sample_metadata.py
from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, PageBreak, KeepTogether
from reportlab.lib import colors
from .styles import h1, normal
from reportlab.lib.units import cm

def build_sample_metadata(data: dict) -> list:
    elements = []
    elements.append(Paragraph("1. Información de la Muestra", h1))
    elements.append(Spacer(1, 0.8*cm))

    table_data = [
        ["Campo", "Valor"],
        ["Material", data['material_name']],
        ["Nombre de la muestra", data['muestra_nombre']],
        ["Fecha del análisis", data['fecha_actual']],
        ["Operador responsable", data['operador_nombre']],
        ["Institución", data['institucion'] or "—"],
    ]

    t = Table(table_data, colWidths=[7*cm, 11*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 13),
        ('FONTSIZE', (0,1), (-1,-1), 12),
        ('GRID', (0,0), (-1,-1), 0.8, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWHEIGHT', (0,0), (-1,-1), 30),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
    ]))

    elements.append(KeepTogether([t, Spacer(1, 2.5*cm)]))
    elements.append(PageBreak())
    return elements