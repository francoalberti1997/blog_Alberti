# reports/utils/pdf/components/conclusions.py
from reportlab.platypus import PageBreak, Paragraph, Spacer, KeepTogether, Image
from .styles import h1, normal
from reportlab.lib.units import cm

# ==================== NUEVOS IMPORTS ====================
import requests
from io import BytesIO
from metalografia.models import Muestra, Micrografia_mask   # ← Ajusta si tu app se llama distinto
# =======================================================


def build_masks(data: dict) -> list:
    elements = []

    # ================================================
    # Texto introductorio (se mantiene igual)
    # ================================================
    text = f"""
    <b>Fecha del reporte:</b> {data['fecha_actual']}<br/><br/>
    <b>Máscaras del análisis microestructural</b><br/><br/>
    Las máscaras detalladas correspondientes al material 
    <b>{data['material_name']}</b> y a la muestra <b>{data['muestra_nombre']}</b> 
    se muestran a continuación.
    """

    elements.append(Paragraph("5. Máscaras", h1))
    elements.append(Spacer(1, 1.0 * cm))
    elements.append(Paragraph(text, normal))
    elements.append(Spacer(1, 1.5 * cm))

    # ================================================
    # NUEVO: Incluir TODAS las imágenes de Micrografia_mask
    # ================================================
    muestra_id = data.get("muestra_id")
    masks = []

    if muestra_id:
        masks = Micrografia_mask.objects.filter(
            micrografia__region__muestra_id=muestra_id
        ).select_related(
            'micrografia',
            'micrografia__region'
        ).order_by('micrografia__region__nombre', 'micrografia__nombre')

    if masks.exists():
        for mask in masks:
            if not mask.imagen:  # si no tiene imagen subidas
                continue

            try:
                # Descargamos la imagen desde Cloudinary
                response = requests.get(mask.imagen.url, timeout=15)
                response.raise_for_status()

                img_data = BytesIO(response.content)

                # Ancho aproximado del contenido del PDF (A4 - márgenes)
                img = Image(img_data, width=15 * cm, height=None)  # mantiene proporción

                # Título de la máscara
                caption = f"""
                <b>Máscara:</b> {mask.nombre}<br/>
                <b>Micrografía:</b> {mask.micrografia.nombre}<br/>
                <b>Región:</b> {mask.micrografia.region.nombre}
                """

                elements.append(Paragraph(caption, normal))
                elements.append(Spacer(1, 0.4 * cm))
                elements.append(KeepTogether([img]))          # evita que se corte entre páginas
                elements.append(Spacer(1, 1.2 * cm))

            except Exception as e:
                # Si falla una imagen, mostramos mensaje pero seguimos con las demás
                elements.append(Paragraph(
                    f"<i>⚠️ No se pudo cargar la máscara {mask.nombre} ({str(e)})</i>",
                    normal
                ))
                elements.append(Spacer(1, 0.8 * cm))

    else:
        elements.append(Paragraph(
            "<i>No se encontraron máscaras para esta muestra.</i>",
            normal
        ))
        elements.append(Spacer(1, 1.0 * cm))

    # ================================================
    # Cierre de sección
    # ================================================
    elements.append(Spacer(1, 2.0 * cm))
    elements.append(PageBreak())

    return elements