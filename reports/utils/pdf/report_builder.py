# reports/utils/pdf/report_builder.py
from pydoc import doc

from cv2 import data
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate
from io import BytesIO

from reports.utils.pdf.material.lcs import build_steel_data
from reports.utils.pdf.material.magnesia import build_magnesia_data


from .cover import build_cover
from .toc import build_toc
from .sample_metadata import build_sample_metadata
from .material_specific import build_material_specific
from .conclusions import build_conclusions
from .masks import build_masks
from datetime import datetime


def first_page(canvas, doc):
    from reportlab.lib import colors
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.dimgray)
    canvas.drawCentredString(doc.width / 2 + doc.leftMargin, 1.5 * cm, f"Fecha: {doc._fecha_actual}")
    canvas.restoreState()

def later_pages(canvas, doc):
    from reportlab.lib import colors
    canvas.saveState()
    header_y = doc.height + doc.topMargin
    canvas.setFillColor(colors.lightsteelblue)
    canvas.rect(doc.leftMargin - 0.4*cm, header_y - 1.0*cm,
                doc.width + 0.8*cm, 1.0*cm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(doc.leftMargin + 0.6*cm, header_y - 0.70*cm, "ANÁLISIS MICROESTRUCTURAL")
    canvas.setFillColor(colors.darkslategray)
    mat_short = doc._material_name[:38] + "..." if len(doc._material_name) > 38 else doc._material_name
    canvas.drawRightString(doc.width + doc.leftMargin - 0.6*cm, header_y - 0.70*cm, mat_short)
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.dimgray)
    canvas.drawCentredString(doc.leftMargin + doc.width / 2, 1.5*cm, f"Página {canvas.getPageNumber()}")
    canvas.drawString(doc.leftMargin + 0.5*cm, 1.5*cm, "Laboratorio de Microscopía • Reporte Técnico")
    canvas.drawRightString(doc.width + doc.leftMargin - 0.5*cm, 1.5*cm, doc._fecha_actual)
    canvas.restoreState()

def build_full_report_pdf(data: dict) -> tuple[bytes, str]:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2.6*cm, rightMargin=2.6*cm,
        topMargin=4.0*cm, bottomMargin=2.8*cm
    )

    
    meta = data["meta"]

    doc._material_name = meta['material_name']
    doc._fecha_actual = meta['fecha_actual']

    elements = []
    elements.extend(build_cover(meta))
    elements.extend(build_toc())
    elements.extend(build_sample_metadata(meta))
    
    #Incluir acá argumentos para incluir secciones específicas según el material
    elements.extend(build_material_specific(data))

    elements.extend(build_masks(meta))
    
    elements.extend(build_conclusions(meta))
    
    doc.build(elements, onFirstPage=first_page, onLaterPages=later_pages)

    buffer.seek(0)
    pdf_bytes = buffer.getvalue()

    meta = data["meta"]

    filename = (
        f"reporte_{meta.get('muestra_id', '000')}_"
        f"{meta['material_name'].replace(' ', '_')}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    )
    return pdf_bytes, filename


MESES_ES = [
    None, 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
]

def build_pdf_data(pdf_obj) -> dict:
    return {
        "meta": build_common_data(pdf_obj),
        "material": build_material_data(pdf_obj)
    }


def build_common_data(pdf_obj) -> dict:
    muestra = pdf_obj.muestra

    operador_nombre = f"{pdf_obj.owner.name} {pdf_obj.owner.surname}"
    institucion = pdf_obj.owner.company.name if pdf_obj.owner.company else ""

    logo_url = (
        pdf_obj.owner.company.image.url
        if pdf_obj.owner.company and pdf_obj.owner.company.image
        else None
    )

    now = datetime.now()
    fecha_actual = f"{now.day} de {MESES_ES[now.month]} de {now.year}"

    return {
        "muestra_id": muestra.id,
        "material_name": "magnesia",  # 👈 clave real
        "muestra_nombre": muestra.nombre,
        "fecha_actual": fecha_actual,
        "operador_nombre": operador_nombre,
        "institucion": institucion,
        "logo_url": logo_url,
    }

def build_material_data(pdf_obj) -> dict:
    material_name = "magnesia" 

    builders = {
        "steel": build_steel_data,
        "magnesia": build_magnesia_data,
    }

    builder = builders.get(material_name)

    if not builder:
        return {}
    
    print(("builder(pdf_obj): ", builder(pdf_obj)))

    return builder(pdf_obj)