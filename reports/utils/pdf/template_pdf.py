# reports/skeleton_pdf_builder.py
import os
import tempfile
import requests
from io import BytesIO
import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    KeepTogether, PageBreak
)
from PIL import Image
from PIL import Image as PILImage
from reportlab.platypus import Image as RLImage


def image_keep_aspect(path, max_width_cm, max_height_cm):
    img = PILImage.open(path)
    w, h = img.size
    aspect = w / h

    max_w = max_width_cm * cm
    max_h = max_height_cm * cm

    if (max_w / aspect) <= max_h:
        width = max_w
        height = max_w / aspect
    else:
        height = max_h
        width = max_h * aspect

    return RLImage(path, width=width, height=height)


def build_skeleton_pdf_content(data: dict) -> tuple[bytes, str]:
    """
    Construye el PDF ESQUELETO COMÚN A TODOS LOS MATERIALES.
    
    Solo usa los campos comunes:
        - material_name
        - muestra_nombre
        - fecha_actual
        - operador_nombre
        - institucion
        - logo_url
    
    El resto de estadísticas (n_grains, sinter_pct, etc.) son específicas
    por material y se agregarán después con tu script por material.
    
    Estructura:
    1. Portada
    2. Índice (con las 5 secciones)
    3. Información de la muestra
    4. Conclusiones (genéricas - sin estadísticas específicas)
    
    Las secciones 2, 3 y 4 del índice (Resumen general, Normas ASTM y Máscaras predichas)
    solo aparecen en el índice. Tú las completarás luego.
    """
    # === SOLO LOS CAMPOS COMUNES ===
    material_name   = data['material_name']
    muestra_nombre  = data['muestra_nombre']
    fecha_actual    = data['fecha_actual']
    operador_nombre = data['operador_nombre']
    institucion     = data['institucion']
    logo_url        = data.get("logo_url")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2.6*cm, rightMargin=2.6*cm,
        topMargin=4.0*cm,
        bottomMargin=2.8*cm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name='Title',
        fontName='Helvetica-Bold',
        fontSize=28,
        textColor=colors.darkblue,
        spaceAfter=32,
        alignment=TA_CENTER,
        leading=34
    )
    h1 = ParagraphStyle(
        name='H1',
        fontName='Helvetica-Bold',
        fontSize=16,
        textColor=colors.darkslategray,
        spaceBefore=22,
        spaceAfter=10,
        alignment=TA_LEFT,
        leading=20
    )
    normal = ParagraphStyle(
        name='Normal',
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        spaceAfter=10
    )

    def first_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.dimgray)
        canvas.drawCentredString(doc.width / 2 + doc.leftMargin, 1.5 * cm, f"Fecha: {fecha_actual}")
        canvas.restoreState()

    def later_pages(canvas, doc):
        canvas.saveState()
        header_y = doc.height + doc.topMargin
        canvas.setFillColor(colors.lightsteelblue)
        canvas.rect(doc.leftMargin - 0.4*cm, header_y - 1.0*cm,
                    doc.width + 0.8*cm, 1.0*cm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(doc.leftMargin + 0.6*cm, header_y - 0.70*cm, "ANÁLISIS MICROESTRUCTURAL")
        canvas.setFillColor(colors.darkslategray)
        canvas.setFont("Helvetica", 9)
        mat_short = material_name[:38] + "..." if len(material_name) > 38 else material_name
        canvas.drawRightString(doc.width + doc.leftMargin - 0.6*cm, header_y - 0.70*cm, mat_short)
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.dimgray)
        page_num = canvas.getPageNumber()
        canvas.drawCentredString(doc.leftMargin + doc.width / 2, 1.5*cm, f"Página {page_num}")
        canvas.drawString(doc.leftMargin + 0.5*cm, 1.5*cm, "Laboratorio de Microscopía • Reporte Técnico")
        canvas.drawRightString(doc.width + doc.leftMargin - 0.5*cm, 1.5*cm, fecha_actual)
        canvas.restoreState()

    elements = []

    # ====================== 1. PORTADA ======================
    logo_path = None
    try:
        if logo_url and logo_url.startswith("http"):
            resp = requests.get(logo_url, timeout=10)
            resp.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(resp.content)
                logo_path = f.name
        else:
            logo_path = logo_url

        if logo_path and os.path.exists(logo_path):
            logo_img = image_keep_aspect(logo_path, 9.5, 5.2)
            logo_img.hAlign = 'CENTER'
            elements.append(logo_img)
            elements.append(Spacer(1, 1.6*cm))
        else:
            elements.append(Spacer(1, 2*cm))

    except Exception:
        elements.append(Spacer(1, 2*cm))

    elements.append(Paragraph("Análisis Microestructural", title_style))
    elements.append(Spacer(1, 1.1*cm))
    elements.append(Paragraph(f"Material: <b>{material_name}</b>", h1))
    elements.append(Paragraph(f"Muestra: <b>{muestra_nombre}</b>", h1))
    elements.append(Spacer(1, 2.0*cm))
    elements.append(Paragraph(f"<b>Fecha:</b> {fecha_actual}", normal))
    elements.append(Paragraph(f"<b>Operador:</b> {operador_nombre}", normal))
    elements.append(Paragraph(f"<b>Institución:</b> {institucion or '—'}", normal))
    elements.append(PageBreak())

    # ====================== 2. ÍNDICE ======================
    elements.append(Paragraph("Índice", h1))
    elements.append(Spacer(1, 1.2*cm))

    index_items = [
        "1. Información de la muestra",
        "2. Resumen general",
        "3. Normas ASTM",
        "4. Máscaras predichas",
        "5. Conclusiones"
    ]

    for item in index_items:
        elements.append(Paragraph(f"• {item}", normal))
        elements.append(Spacer(1, 0.5*cm))

    elements.append(Spacer(1, 2.0*cm))
    elements.append(PageBreak())

    # ====================== 3. INFORMACIÓN DE LA MUESTRA ======================
    elements.append(Paragraph("1. Información de la Muestra", h1))
    elements.append(Spacer(1, 0.8*cm))

    info_table_data = [
        ["Campo", "Valor"],
        ["Material", material_name],
        ["Nombre de la muestra", muestra_nombre],
        ["Fecha del análisis", fecha_actual],
        ["Operador responsable", operador_nombre],
        ["Institución", institucion or "—"],
    ]

    info_table = Table(info_table_data, colWidths=[7*cm, 11*cm])
    info_style = TableStyle([
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
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
    ])
    info_table.setStyle(info_style)

    elements.append(KeepTogether([info_table, Spacer(1, 2.5*cm)]))
    elements.append(PageBreak())

    # ====================== 5. CONCLUSIONES (GENÉRICAS) ======================
    conclusion_text = f"""
    <b>Fecha del reporte:</b> {fecha_actual}<br/><br/>
    <b>Conclusiones del análisis microestructural</b><br/><br/>
    Las conclusiones detalladas correspondientes al material <b>{material_name}</b> 
    y a la muestra <b>{muestra_nombre}</b> se encuentran en la sección específica 
    del material (se insertarán automáticamente por el script correspondiente).
    """

    elements.append(Paragraph("5. Conclusiones", h1))
    elements.append(Spacer(1, 1.0*cm))
    elements.append(Paragraph(conclusion_text, normal))
    elements.append(Spacer(1, 3.0*cm))

    # ====================== CONSTRUIR PDF ======================
    doc.build(elements, onFirstPage=first_page, onLaterPages=later_pages)

    # Limpieza temporal del logo
    if logo_path and logo_path.startswith("/tmp/") and os.path.exists(logo_path):
        try:
            os.unlink(logo_path)
        except:
            pass

    buffer.seek(0)
    pdf_bytes = buffer.getvalue()

    filename = f"esqueleto_reporte_{data.get('muestra_id', '000')}_{material_name.replace(' ', '_')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

    return pdf_bytes, filename