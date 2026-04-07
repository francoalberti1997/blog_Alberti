# reports/pdf_builder.py
import os
import tempfile
import requests
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, KeepTogether, PageBreak
)
import datetime

from .utils import image_keep_aspect



def build_pdf_content(data: dict) -> tuple[bytes, str]:
    """
    Construye el PDF a partir de datos preprocesados.
    Retorna (pdf_bytes, filename_sugerido)
    """
    # Desempaquetar datos
    material_name       = data['material_name']
    muestra_nombre      = data['muestra_nombre']
    fecha_actual        = data['fecha_actual']
    operador_nombre     = data['operador_nombre']
    institucion         = data['institucion']
    n_grains            = data['n_grains']
    len_sinter          = data['len_sinter']
    len_electro         = data['len_electro']
    sinter_pct          = data['sinter_pct']
    electro_pct         = data['electro_pct']
    dominant_label      = data['dominant_label']
    n_calidades         = data['n_calidades']
    calidad_table_data  = data['calidad_table_data']
    dist_plot_path      = data.get('dist_plot_path')
    muestra_imagen_path = data.get('muestra_imagen_path')
    regions             = data['regions']  # lista de dicts
    logo_url = data["logo_url"]
    invalid_micrographs = data.get("invalid_micrographs", [])

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
    h2 = ParagraphStyle(
        name='H2',
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=colors.slategray,
        spaceBefore=18,
        spaceAfter=8,
        alignment=TA_LEFT,
        leading=18
    )
    normal = ParagraphStyle(
        name='Normal',
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        spaceAfter=10
    )
    caption = ParagraphStyle(
        name='Caption',
        fontName='Helvetica-Oblique',
        fontSize=12,
        leading=15,
        textColor=colors.dimgray,
        alignment=TA_CENTER,
        spaceBefore=12,
        spaceAfter=18
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

    # PORTADA
    
    logo_temp_path = None
    
    logo = data["logo_url"]
    logo_path = None

    try:
        if logo and logo.startswith("http"):
            resp = requests.get(logo, timeout=10)
            resp.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(resp.content)
                logo_path = f.name
        else:
            logo_path = logo

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
    elements.append(Paragraph(f"<b>Institución:</b> {institucion}", normal))
    elements.append(PageBreak())

    # RESUMEN
    summary_table = Table([
        ["Parámetro", "Valor", "Notas"],
        ["Granos analizados", n_grains, ""],
        ["Calidad dominante", dominant_label, ""],
        ["Granos sinterizados", f"{len_sinter} ({sinter_pct:.1f}%)", "Calidades 1–4"],
        ["Granos electrofundidos", f"{len_electro} ({electro_pct:.1f}%)", "Calidades 5–10"],
    ], colWidths=[8*cm, 5*cm, 5.5*cm])

    summary_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 13),
        ('GRID', (0,0), (-1,-1), 1, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWHEIGHT', (0,0), (-1,-1), 32),
        ('LEFTPADDING', (0,0), (-1,-1), 15),
        ('RIGHTPADDING', (0,0), (-1,-1), 15),
    ])
    for row in range(1, 5):
        bg = colors.whitesmoke if row % 2 == 1 else colors.white
        summary_style.add('BACKGROUND', (0, row), (-1, row), bg)
    summary_table.setStyle(summary_style)

    elements.append(KeepTogether([
        Paragraph("Resumen estadístico", h1),
        Spacer(1, 0.7*cm),
        summary_table
    ]))
    elements.append(Spacer(1, 1.8*cm))

    # CLASIFICACIÓN POR CALIDADES
    t_cal = Table(calidad_table_data, colWidths=[9*cm, 5.5*cm, 3.5*cm, 3.5*cm])
    t_cal.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 13),
        ('GRID', (0,0), (-1,-1), 0.8, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWHEIGHT', (0,0), (-1,-1), 28),
    ]))
    elements.append(KeepTogether([
        Paragraph("Clasificación por calidades (estándar industrial)", h1),
        Spacer(1, 0.7*cm),
        t_cal
    ]))
    elements.append(Spacer(1, 1.6*cm))


    final_path = None

    if muestra_imagen_path:
        if str(muestra_imagen_path).startswith("http"):
            resp = requests.get(muestra_imagen_path, timeout=10)
            resp.raise_for_status()

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(resp.content)
                final_path = f.name
        else:
            final_path = muestra_imagen_path

    if final_path and os.path.exists(final_path):
        elements.append(KeepTogether([
            image_keep_aspect(final_path, 16.5, 11),
            Paragraph("Figura 1. Aspecto general de la muestra.", caption)
        ]))

    # GRÁFICO DE DISTRIBUCIÓN
    if dist_plot_path and os.path.exists(dist_plot_path):
        img = Image(dist_plot_path, width=19.2*cm, height=11.8*cm)
        img.hAlign = 'CENTER'
        elements.append(Spacer(1, 0.6*cm))
        elements.append(KeepTogether([
            img,
            Spacer(1, 0.6*cm),
            Paragraph("Figura 2. Distribución del tamaño de cristal por calidad.", caption)
        ]))
        elements.append(Spacer(1, 1.2*cm))

    fig_num = 3
    for region_data in regions:
        region_block = []
        region_block.append(Paragraph(region_data['titulo'], h1))
        region_block.append(Spacer(1, 1.0*cm))

        print(f"Procesando imagen de región '{region_data['nombre']}': {region_data.get('imagen_path')}")

        # === IMAGEN GENERAL DE LA REGIÓN ===
        imagen_path = region_data.get('imagen_path')
        if imagen_path:
            final_path = None

            if str(imagen_path).startswith(("http", "https")):
                try:
                    resp = requests.get(imagen_path, timeout=15)
                    resp.raise_for_status()

                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                        f.write(resp.content)
                        final_path = f.name
                    print(f"Imagen región '{region_data['nombre']}' descargada temporalmente: {final_path}")
                except Exception as e:
                    print(f"Error descargando imagen de región {region_data['nombre']}: {e}")
                    final_path = None
            else:
                final_path = imagen_path

            if final_path and os.path.exists(final_path):
                region_block.append(KeepTogether([
                    image_keep_aspect(final_path, 15.5, 10.2),
                    Spacer(1, 0.5*cm),
                    Paragraph(f"Figura {fig_num}. Región {region_data['nombre']} – Vista general.", caption),
                    Spacer(1, 1.4*cm),
                ]))
                fig_num += 1
            else:
                region_block.append(Paragraph(
                    f"Figura {fig_num}. Región {region_data['nombre']} – [Imagen no disponible]", 
                    caption
                ))
                fig_num += 1

        # === CALIDADES Y FIGURAS ===
        for cal_block in region_data['calidades']:
            print(f"Procesando bloque de calidad '{cal_block['label']}' en región '{region_data['nombre']}' con {len(cal_block['figuras'])} figuras.")

            calidad_subblock = []
            calidad_subblock.append(Paragraph(cal_block['label'], 
                                            h1 if cal_block['id'] <= 4 else h2))
            calidad_subblock.append(Spacer(1, 0.6*cm))

            for fig_data in cal_block['figuras']:
                print(f"Procesando figura: {fig_data.get('caption')}")

                fig_path = fig_data.get('path')
                final_fig_path = None

                if fig_path and str(fig_path).startswith(("http", "https")):
                    try:
                        resp = requests.get(fig_path, timeout=20)
                        resp.raise_for_status()

                        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                            f.write(resp.content)
                            final_fig_path = f.name
                        print(f"✓ Figura descargada temporalmente: {final_fig_path}")
                    except Exception as e:
                        print(f"✗ Error descargando figura: {e}")
                        final_fig_path = None
                else:
                    final_fig_path = fig_path

                if final_fig_path and os.path.exists(final_fig_path):
                    calidad_subblock.append(KeepTogether([
                        image_keep_aspect(final_fig_path, 13.0, 9.3),
                        Spacer(1, 0.45*cm),
                        Paragraph(
                            f"Figura {fig_num}. {fig_data['caption']}",
                            caption
                        ),
                        Spacer(1, 1.1*cm),
                    ]))
                    fig_num += 1
                else:
                    calidad_subblock.append(KeepTogether([
                        Paragraph(
                            f"Figura {fig_num}. {fig_data.get('caption', 'Sin nombre')} – [Imagen no disponible]", 
                            caption
                        ),
                        Spacer(1, 0.8*cm)
                    ]))
                    fig_num += 1

            region_block.append(KeepTogether(calidad_subblock))

        # === AGREGAR LA REGIÓN COMPLETA AL PDF ===
        region_block.append(Spacer(1, 2.0*cm))
        elements.append(KeepTogether(region_block))
        print(f"✓ Región '{region_data['nombre']}' agregada al PDF")


    if invalid_micrographs:
        elements.append(PageBreak())

        elements.append(Paragraph("Micrografías no procesadas", h1))
        elements.append(Spacer(1, 0.8*cm))

        elements.append(Paragraph(
            "Las siguientes micrografías no pudieron ser analizadas automáticamente "
            "debido a problemas en la detección de bordes de cristal. "
            "No fueron consideradas en los cálculos estadísticos.",
            normal
        ))
        elements.append(Spacer(1, 1.2*cm))

        for micro in invalid_micrographs:
            block = []
            micro_name = micro.get('nombre', 'Micrografía sin nombre')
            image_url = micro.get("path") or micro.get("imagen_url") or micro.get("image_url")

            print(f"Procesando micrografía inválida: {micro_name} | URL: {image_url}")

            final_micro_path = None

            if image_url and str(image_url).startswith(("http", "https")):
                try:
                    resp = requests.get(image_url, timeout=15)
                    resp.raise_for_status()

                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                        f.write(resp.content)
                        final_micro_path = f.name
                    print(f"✓ Micro inválida descargada: {final_micro_path}")
                except Exception as e:
                    print(f"✗ Error descargando micro inválida {micro_name}: {e}")
                    final_micro_path = None
            else:
                final_micro_path = image_url

            if final_micro_path and os.path.exists(final_micro_path):
                block.append(KeepTogether([
                    image_keep_aspect(final_micro_path, 13.0, 9.3),
                    Spacer(1, 0.4*cm),
                    Paragraph(micro_name, caption),
                    Spacer(1, 1.0*cm)
                ]))
            else:
                block.append(KeepTogether([
                    Paragraph(f"{micro_name} – [Imagen no disponible]", caption),
                    Spacer(1, 1.0*cm)
                ]))

            elements.append(KeepTogether(block))

    # CONCLUSIONES
    conclusion_text = f"""
    <b>Fecha del reporte:</b> {fecha_actual}<br/><br/>
    <b>Resumen final:</b><br/>
    • Total de granos analizados: <b>{n_grains}</b><br/>
    • Granos sinterizados: <b>{len_sinter} ({sinter_pct:.1f}%)</b> – Calidades 1 a 4<br/>
    • Granos electrofundidos: <b>{len_electro} ({electro_pct:.1f}%)</b> – Calidades 5 a 10<br/><br/>
    Calidades identificadas: <b>{n_calidades}</b><br/>
    Calidad más frecuente: <b>{dominant_label}</b>
    """
    elements.append(PageBreak())
    elements.append(KeepTogether([
        Paragraph("Conclusiones", h1),
        Spacer(1, 1.0*cm),
        Paragraph(conclusion_text, normal),
        Spacer(1, 2.0*cm),
    ]))

    # Construir el PDF
    doc.build(elements, onFirstPage=first_page, onLaterPages=later_pages)

    # Limpieza de temporales
    if dist_plot_path and os.path.exists(dist_plot_path):
        try:
            os.unlink(dist_plot_path)
        except:
            pass
    if logo_temp_path and os.path.exists(logo_temp_path):
        try:
            os.unlink(logo_temp_path)
        except:
            pass

    buffer.seek(0)
    pdf_bytes = buffer.getvalue()
    filename = f"reporte_{data['muestra_id']}_{material_name.replace(' ', '_')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

    return pdf_bytes, filename