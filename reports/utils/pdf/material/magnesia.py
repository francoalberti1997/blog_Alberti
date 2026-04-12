import numpy as np
from collections import Counter
import os
from reportlab.platypus import Paragraph, PageBreak, Image, KeepTogether, Spacer, Table, TableStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from metalografia.utils.utils import (
    image_keep_aspect,
    create_quality_distribution_plot,
    create_crystals_distribution_plot
)
from ..styles import h1, h2, normal, normal_bold

from metalografia.models import Region
import requests
from io import BytesIO
from PIL import Image as PILImage


# ================== CALIDADES ======================
GRAIN_QUALITIES = [
    (0, 90),       # Calidad 1
    (100, 200),    # Calidad 2
    (200, 250),    # Calidad 3
    (300, 350),    # Calidad 4
    (400, 500),    # Calidad 5
    (550, 600),    # Calidad 6
    (600, 700),    # Calidad 7
    (700, 800),    # Calidad 8
    (800, 900),    # Calidad 9
    (901, float("inf")),  # Calidad 10
]


def get_quality(size):
    for i, (low, high) in enumerate(GRAIN_QUALITIES, start=1):
        if low <= size <= high:
            return i
    return None


def get_quality_range(q: int) -> str:
    """Devuelve el rango teórico definido para cada calidad"""
    if 1 <= q <= 10:
        low, high = GRAIN_QUALITIES[q - 1]
        if high == float("inf"):
            return f"{low} - ∞"
        return f"{low} - {high}"
    return "—"


# ====================== BUILD DATA ======================
def build_magnesia_data(pdf_obj) -> dict:
    sample = pdf_obj.muestra
    regions = Region.objects.filter(muestra=sample).prefetch_related(
        'region_measure', 'micrografias__measure_micro'
    )

    grain_sizes = []    
    region_data = {}

    for region in regions:
        print(f"Procesando grano: {region.nombre}")
        if not hasattr(region, 'region_measure') or region.region_measure.mean_size is None:
            continue

        mean_um = round(region.region_measure.mean_size, 2)
        grain_sizes.append(mean_um)

        micro_data = []
        for micro in region.micrografias.all():
            if not hasattr(micro, 'measure_micro') or micro.measure_micro.mean_size is None:
                continue
            if micro.um_by_px is None:
                continue

            measure = micro.measure_micro

            mean_um_micro = round(measure.mean_size * micro.um_by_px, 2)
            std_um_micro = round(measure.standard_deviation * micro.um_by_px, 2) \
                if measure.standard_deviation else None

            # Imagen original de la micrografía
            micro_image_url = (
                micro.imagen.url if hasattr(micro.imagen, 'url') else str(micro.imagen)
            ) if micro.imagen else None

            # Imagen de medición (MicrographyMeasure.imagen)
            measure_image_url = None
            if hasattr(measure, 'imagen') and measure.imagen:
                measure_image_url = (
                    measure.imagen.url if hasattr(measure.imagen, 'url') else str(measure.imagen)
                )

            micro_entry = {
                'nombre': micro.nombre,
                'imagen': micro_image_url,           # Imagen original
                'measure_imagen': measure_image_url, # Imagen de medición / máscara
                'mean_um': mean_um_micro,
                'std_um': std_um_micro,
                'distribution_um': None,
            }

            # === EXTRAER DISTRIBUCIÓN COMPLETA ===
            try:
                if measure and measure.distribution_quantiles:
                    quantiles = measure.distribution_quantiles
                    
                    px_values = None
                    
                    if isinstance(quantiles, dict):
                        q_keys = [k for k in quantiles.keys() if str(k).lower().startswith('q')]
                        if q_keys:
                            sorted_q_keys = sorted(q_keys, key=lambda x: int(str(x)[1:]))
                            px_values = np.array([float(quantiles[k]) for k in sorted_q_keys])
                        else:
                            px_values = np.array([float(v) for v in quantiles.values()])
                    else:
                        px_values = np.array(quantiles, dtype=float)

                    um_by_px = micro.um_by_px
                    if um_by_px is not None and px_values is not None:
                        distribution_um = (px_values * um_by_px).tolist()
                    else:
                        distribution_um = px_values.tolist() if px_values is not None else []

                    micro_entry['distribution_um'] = distribution_um
                    
                    print(f"✓ Micro {micro.nombre}: {len(distribution_um)} puntos extraídos")

                else:
                    print(f"⚠ Micro {micro.nombre}: No tiene distribution_quantiles")
                    micro_entry['distribution_um'] = []

            except Exception as e:
                print(f"❌ Error al extraer distribution_quantiles de micro {micro.nombre}: {e}")
                micro_entry['distribution_um'] = []

            micro_data.append(micro_entry)

        # Imagen del grano (región)
        region_image = None
        if region.imagen:
            region_image = (
                region.imagen.url if hasattr(region.imagen, 'url') else str(region.imagen)
            )

        region_data[region.nombre] = {
            'mean_um': mean_um,
            'micrografias': micro_data,
            'n_micro': len(micro_data),
            'imagen': region_image,
        }

    n_grains = len(grain_sizes)

    if grain_sizes:
        min_um = round(min(grain_sizes), 1)
        max_um = round(max(grain_sizes), 1)

        qualities = [get_quality(size) for size in grain_sizes if get_quality(size) is not None]
        quality_counts = Counter(qualities)

        dominant_quality = f"Calidad {quality_counts.most_common(1)[0][0]}" if quality_counts else "—"

        sinter_count = sum(1 for s in grain_sizes if s <= 400)
        total_valid = len(grain_sizes)
        sinter_pct = (sinter_count / total_valid * 100) if total_valid > 0 else 0.0
        electro_pct = 100.0 - sinter_pct

        quality_hist_path = create_quality_distribution_plot(
            qualities,
            title="Distribución de Calidades de Grano"
        )

    else:
        min_um = max_um = None
        dominant_quality = "—"
        sinter_pct = electro_pct = 0.0
        quality_hist_path = None
        quality_counts = Counter()

    print(f"n_grains: {n_grains}")

    return {
        "n_grains": n_grains,
        "global_um_range": (min_um, max_um),
        "dominant_quality": dominant_quality,
        "sinter_pct": sinter_pct,
        "electro_pct": electro_pct,
        "quality_hist_path": quality_hist_path,
        "region_data": region_data,
        "quality_counts": dict(quality_counts),
    }


# ====================== BUILD PDF ======================
def build_magnesia(data: dict) -> list:
    material = data.get("material") or data
    region_data = material.get("region_data", {})
    
    elements = [
        Paragraph("2. Magnesia - Resumen", h1),
        Spacer(1, 0.8 * cm),
    ]

    # ====================== DATOS GENERALES ======================
    general_data = [
        ["Descripción", "Valor"],
        ["Número de granos analizadas", str(material.get('n_grains', '—'))],
        ["Rango global de tamaños", f"{material.get('global_um_range', (None, None))[0] or '—'} – "
                                    f"{material.get('global_um_range', (None, None))[1] or '—'} µm"],
        ["Calidad dominante", material.get('dominant_quality', '—')],
        ["Proporción sinterizado", f"{material.get('sinter_pct', 0):.1f}%"],
        ["Proporción electrofundido", f"{material.get('electro_pct', 0):.1f}%"],
    ]

    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ECF0F1')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])

    general_table = Table(general_data, colWidths=[8*cm, 9*cm])
    general_table.setStyle(table_style)

    elements.extend([
        Paragraph("Datos generales de la muestra", h2),
        Spacer(1, 0.6 * cm),
        general_table,
        Spacer(1, 1.5 * cm),
    ])

    # ====================== ANÁLISIS POR CALIDADES ======================
    elements.append(Paragraph("Análisis Estadístico de la Muestra (basado en Calidades)", h2))

    if material.get("quality_hist_path") and os.path.exists(material.get("quality_hist_path")):
        try:
            img_qual = image_keep_aspect(material["quality_hist_path"], 16.5, 11.0)
            elements.extend([
                KeepTogether([
                    img_qual,
                    Spacer(1, 0.4 * cm),
                    Paragraph("Figura 1. Histograma de Frecuencia por Calidad de Grano", normal)
                ]),
                Spacer(1, 1.2 * cm)
            ])
        except Exception as e:
            print(f"Error al cargar histograma de calidades: {e}")

    quality_counts = material.get("quality_counts", {})
    total_grains = sum(quality_counts.values())

    quality_table_data = [["Calidad", "Cantidad de granos", "Proporción (%)", "Rango (µm)"]]

    for q in range(1, 11):
        count = quality_counts.get(q, 0)
        range_str = get_quality_range(q)

        proportion_str = f"{(count / total_grains * 100):.1f}%" if total_grains > 0 else "—"

        quality_table_data.append([
            f"Calidad {q}",
            str(count),
            proportion_str,
            range_str
        ])

    quality_table = Table(quality_table_data, colWidths=[5*cm, 5*cm, 3*cm, 3*cm])
    quality_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')),
    ]))

    elements.extend([
        Paragraph("Resumen por Calidad", normal_bold),
        Spacer(1, 0.5 * cm),
        quality_table,
        Spacer(1, 1.5 * cm)
    ])

    # ====================== DETALLE POR GRANO ======================
    elements.append(PageBreak())
    detailed_section = [
        Paragraph("Análisis detallado por grano", h2),
        Spacer(1, 0.3 * cm),
    ]

    for region_name, rdata in region_data.items():
        region_flowables = [
            Paragraph(f"Grano: {region_name}", h2),
            Spacer(1, 0.3 * cm),
            Paragraph(f"Tamaño medio de cristal: {rdata.get('mean_um', '—')} µm", normal),
            Spacer(1, 0.4 * cm),
        ]

        # Imagen principal del grano
        if rdata.get('imagen'):
            try:
                response = requests.get(rdata['imagen'], timeout=25)
                response.raise_for_status()
                img_data = BytesIO(response.content)
                pil_img = PILImage.open(img_data)
                iw, ih = pil_img.size
                aspect = iw / float(ih)

                max_width = 15 * cm
                max_height = 9 * cm
                width = max_width
                height = width / aspect
                if height > max_height:
                    height = max_height
                    width = height * aspect

                img_data.seek(0)
                img_region = Image(img_data, width=width, height=height)

                region_flowables.extend([
                    KeepTogether([
                        img_region,
                        Spacer(1, 0.2 * cm),
                        Paragraph(f"Imagen – {region_name}", normal)
                    ]),
                    Spacer(1, 0.6 * cm)
                ])
            except Exception as e:
                print(f"Error cargando imagen de grano '{region_name}': {e}")
                region_flowables.append(Paragraph(f"⚠ No se pudo cargar la imagen del grano: {region_name}", normal))
                region_flowables.append(Spacer(1, 0.5 * cm))
        else:
            region_flowables.extend([
                Paragraph("No hay imagen de grano cargada.", normal),
                Spacer(1, 0.6 * cm)
            ])

        # ====================== HISTOGRAMA DE DISTRIBUCIÓN DEL GRANO ======================
        all_distribution_values = []
        region_mean_um = rdata.get('mean_um')

        for micro in rdata.get('micrografias', []):
            dist = micro.get('distribution_um')
            if dist and len(dist) >= 5:
                all_distribution_values.extend(dist)
            elif micro.get('mean_um') is not None:
                all_distribution_values.append(micro['mean_um'])  # fallback

        print(f"Total puntos para histograma de '{region_name}': {len(all_distribution_values)}")

        if len(all_distribution_values) >= 5:
            try:
                hist_path = create_crystals_distribution_plot(
                    np.array(all_distribution_values),
                    title=f"Distribución del tamaño de los cristales - grano {region_name}",
                    highlight_value=region_mean_um,
                    highlight_label=f"Media del grano: {region_mean_um:.2f} µm",
                    highlight_color='red'
                )
                
                if hist_path and os.path.exists(hist_path):
                    img_hist = image_keep_aspect(hist_path, 14.5, 8.5)
                    region_flowables.extend([
                        KeepTogether([
                            img_hist,
                            Spacer(1, 0.2 * cm),
                            Paragraph(f"Figura 2. Distribución por micrografía - {region_name} (µm)", normal)
                        ]),
                        Spacer(1, 0.6 * cm)
                    ])
            except Exception as e:
                print(f"Error creando histograma de grano {region_name}: {e}")
        else:
            region_flowables.append(Paragraph("No hay suficientes datos de distribución para generar el histograma.", normal))
            region_flowables.append(Spacer(1, 0.6 * cm))

        # ====================== MICROGRAFÍAS INDIVIDUALES ======================
        if rdata.get('micrografias'):
            micro_section = [
                Paragraph("Micrografías analizadas para los cálculos del grano: " + region_name, normal_bold),
                Spacer(1, 0.3 * cm)
            ]

            for micro in rdata['micrografias']:
                try:
                    # ==================== IMAGEN ORIGINAL ====================
                    if micro.get('imagen'):
                        response = requests.get(micro['imagen'], timeout=25)
                        response.raise_for_status()
                        img_data = BytesIO(response.content)
                        pil_img = PILImage.open(img_data)
                        iw, ih = pil_img.size
                        aspect = iw / float(ih)

                        max_w = 15 * cm
                        max_h = 9 * cm
                        w = max_w
                        h = w / aspect
                        if h > max_h:
                            h = max_h
                            w = h * aspect

                        img_data.seek(0)
                        img_micro = Image(img_data, width=w, height=h)

                        caption = (f"{micro['nombre']} — Original "
                                  f"(Tamaño medio: {micro['mean_um']} µm "
                                  f"± {micro.get('std_um') or '—'} µm)")

                        micro_section.extend([
                            KeepTogether([
                                img_micro,
                                Spacer(1, 0.2 * cm),
                                Paragraph(caption, normal)
                            ]),
                            Spacer(1, 0.6 * cm)
                        ])

                    # ==================== IMAGEN DE MEDICIÓN ====================
                    if micro.get('measure_imagen'):
                        response = requests.get(micro['measure_imagen'], timeout=25)
                        response.raise_for_status()
                        img_data = BytesIO(response.content)
                        pil_img = PILImage.open(img_data)
                        iw, ih = pil_img.size
                        aspect = iw / float(ih)

                        max_w = 15 * cm
                        max_h = 9 * cm
                        w = max_w
                        h = w / aspect
                        if h > max_h:
                            h = max_h
                            w = h * aspect

                        img_data.seek(0)
                        img_measure = Image(img_data, width=w, height=h)

                        micro_section.extend([
                            KeepTogether([
                                img_measure,
                                Spacer(1, 0.2 * cm),
                                Paragraph(f"{micro['nombre']} — Imagen de medición / máscara", normal)
                            ]),
                            Spacer(1, 0.7 * cm)
                        ])

                except Exception as e:
                    print(f"Error cargando micrografía '{micro.get('nombre')}': {e}")
                    micro_section.extend([
                        Paragraph(f"⚠ No se pudo cargar la imagen: {micro.get('nombre', 'Sin nombre')}", normal),
                        Spacer(1, 0.5 * cm)
                    ])

            region_flowables.append(KeepTogether(micro_section))
        else:
            region_flowables.extend([
                Paragraph("No hay micrografías cargadas para este grano.", normal),
                Spacer(1, 0.6 * cm)
            ])

        detailed_section.extend(region_flowables)
        detailed_section.append(Spacer(1, 0.4 * cm))

    elements.append(KeepTogether(detailed_section))
    elements.append(PageBreak())

    return elements