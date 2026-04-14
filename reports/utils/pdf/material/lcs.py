import numpy as np
from collections import Counter
import os
import math
from reportlab.platypus import Paragraph, PageBreak, Image, KeepTogether, Spacer, Table, TableStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from metalografia.utils.utils import (
    image_keep_aspect,
    create_intercept_distribution_plot
)
from ..styles import h1, h2, normal, normal_bold

from metalografia.models import Region
import requests
from io import BytesIO
from PIL import Image as PILImage


# ====================== DES-ESCALADO (factor 1.5) ======================
def true_intercept_um(scaled_um: float) -> float:
    """Convierte el valor escalado almacenado en DB al intercepto real en µm"""
    return round(scaled_um / 1.5, 2) if scaled_um is not None else None


# ====================== CONVERSIÓN ASTM (MÉTODO DE INTERCEPTOS) ======================
def get_astm_grain_size(scaled_mean_um: float) -> float | None:
    """Convierte el valor escalado de la DB al ASTM G correcto"""
    if scaled_mean_um is None or scaled_mean_um <= 0:
        return None
    
    # Primero obtenemos el intercepto real
    L_mm = true_intercept_um(scaled_mean_um) / 1000.0
    G = -6.6457 * np.log10(L_mm) - 3.298
    return round(G, 2)


# ====================== BUILD DATA ======================
def build_steel_data(pdf_obj) -> dict:
    sample = pdf_obj.muestra
    regions = Region.objects.filter(muestra=sample).prefetch_related(
        'region_measure', 'micrografias__measure_micro'
    )

    grain_sizes_real = []      # ← valores reales (des-escalados)
    astm_sizes = []
    region_data = {}

    for region in regions:
        if not hasattr(region, 'region_measure') or region.region_measure.mean_size is None:
            continue

        scaled_mean = region.region_measure.mean_size
        real_mean_um = true_intercept_um(scaled_mean)          # ← valor real para gráficos y texto

        grain_sizes_real.append(real_mean_um)

        astm = get_astm_grain_size(scaled_mean)
        if astm is not None:
            astm_sizes.append(astm)

        # Micrografías
        micro_data = []
        for micro in region.micrografias.all():
            if not hasattr(micro, 'measure_micro') or micro.measure_micro.mean_size is None:
                continue
            if micro.um_by_px is None:
                continue

            measure = micro.measure_micro
            scaled_um_micro = measure.mean_size * micro.um_by_px
            real_um_micro = true_intercept_um(scaled_um_micro)

            std_um_micro = round(measure.standard_deviation * micro.um_by_px / 1.5, 2) \
                if measure.standard_deviation else None

            micro_image_url = (micro.imagen.url if hasattr(micro.imagen, 'url') else str(micro.imagen)) if micro.imagen else None
            measure_image_url = (measure.imagen.url if hasattr(measure, 'imagen') and measure.imagen else None)

            micro_entry = {
                'nombre': micro.nombre,
                'imagen': micro_image_url,
                'measure_imagen': measure_image_url,
                'mean_um': real_um_micro,           # ← valor real
                'std_um': std_um_micro,
                'distribution_um': None,
            }

            # Distribución real (des-escalada)
            try:
                if measure and measure.distribution_quantiles:
                    quantiles = measure.distribution_quantiles
                    if isinstance(quantiles, dict):
                        q_keys = [k for k in quantiles.keys() if str(k).lower().startswith('q')]
                        sorted_q_keys = sorted(q_keys, key=lambda x: int(str(x)[1:])) if q_keys else list(quantiles.keys())
                        px_values = np.array([float(quantiles[k]) for k in sorted_q_keys])
                    else:
                        px_values = np.array(quantiles, dtype=float)
                    dist_scaled = (px_values * micro.um_by_px).tolist()
                    dist_real = [true_intercept_um(v) for v in dist_scaled]
                    micro_entry['distribution_um'] = dist_real
            except Exception:
                micro_entry['distribution_um'] = []

            micro_data.append(micro_entry)

        # Distribución completa de la región (valores reales)
        all_distribution_real = []
        for micro in micro_data:
            dist = micro.get('distribution_um')
            if dist and len(dist) >= 5:
                all_distribution_real.extend(dist)
            elif micro.get('mean_um') is not None:
                all_distribution_real.append(micro['mean_um'])

        region_image = (region.imagen.url if hasattr(region.imagen, 'url') else str(region.imagen)) if region.imagen else None

        region_data[region.nombre] = {
            'mean_um': real_mean_um,                    # ← valor real para mostrar
            'astm': astm,
            'micrografias': micro_data,
            'n_micro': len(micro_data),
            'imagen': region_image,
            'distribution_um': all_distribution_real,
            'n_points': len(all_distribution_real),
        }

    # Estadísticos globales (con valores reales)
    n_grains = len(grain_sizes_real)
    quality_hist_path = None

    if grain_sizes_real:
        min_um = round(min(grain_sizes_real), 1)
        max_um = round(max(grain_sizes_real), 1)
        avg_um = round(sum(grain_sizes_real) / n_grains, 2)

        if astm_sizes:
            avg_astm = round(sum(astm_sizes) / len(astm_sizes), 2)
            min_astm = round(min(astm_sizes), 2)
            max_astm = round(max(astm_sizes), 2)
        else:
            avg_astm = min_astm = max_astm = None

        quality_hist_path = create_intercept_distribution_plot(
            grain_sizes_real,
            title="Distribución de Longitud Media de Intercepto",
            highlight_value=avg_um,
            highlight_label=f"Media global = {avg_um:.2f} µm"
        )
    else:
        min_um = max_um = avg_um = None
        avg_astm = min_astm = max_astm = None

    return {
        "n_grains": n_grains,
        "global_um_range": (min_um, max_um),
        "avg_um": avg_um,
        "global_astm_range": (min_astm, max_astm),
        "avg_astm": avg_astm,
        "quality_hist_path": quality_hist_path,
        "region_data": region_data,
    }


# ====================== BUILD PDF ======================
def build_steel(data: dict) -> list:
    material = data.get("material") or data
    region_data = material.get("region_data", {})

    elements = [
        Paragraph("2. Acero - Resumen", h1),
        Spacer(1, 0.4 * cm),
    ]

    # ECUACIÓN ASTM G
    elements.extend([
        Paragraph("El número ASTM G se calcula a partir de la longitud media de intercepto (µm) "
                  "utilizando la siguiente ecuación (norma ASTM E112, Tabla 6):", normal),
        Paragraph("G = −6.6457 × log(L_mm) − 3.298", normal_bold),
        Paragraph("donde:", normal),
        Paragraph("• L_mm = longitud media de intercepto en mm (= valor_almacenado / 1500)", normal),
        Spacer(1, 0.8 * cm),
    ])

    # DATOS GENERALES
    general_data = [
        ["Descripción", "Valor"],
        ["Número de regiones analizadas", str(material.get('n_grains', '—'))],
        ["Rango global de longitudes de intercepto", f"{material.get('global_um_range', (None, None))[0] or '—'} – "
                                                    f"{material.get('global_um_range', (None, None))[1] or '—'} µm"],
        ["Longitud media de intercepto global", f"{material.get('avg_um', '—')} µm"],
        ["Rango ASTM G de la muestra", f"{material.get('global_astm_range', (None, None))[0] or '—'} – "
                                       f"{material.get('global_astm_range', (None, None))[1] or '—'}"],
    ]

    general_table = Table(general_data, colWidths=[8*cm, 9*cm])
    general_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ECF0F1')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.extend([
        Paragraph("Datos generales de la muestra", h2),
        Spacer(1, 0.6 * cm),
        general_table,
        Spacer(1, 1.0 * cm),
    ])

    # HISTOGRAMA GLOBAL
    if material.get("quality_hist_path"):
        try:
            hist_img = image_keep_aspect(material["quality_hist_path"], 15, 9)
            elements.extend([
                KeepTogether([
                    hist_img,
                    Spacer(1, 0.2 * cm),
                    Paragraph("Figura 1. Distribución global de longitud media de intercepto (µm)", normal)
                ]),
                Spacer(1, 1.2 * cm)
            ])
        except Exception as e:
            elements.append(Paragraph(f"⚠ No se pudo cargar el histograma global: {e}", normal))
    else:
        elements.append(Paragraph("⚠ No se generó histograma global (menos de 2 regiones)", normal))

    # elements.append(PageBreak())

    # ====================== DETALLE POR REGIÓN ======================
    detailed_section = [Paragraph("Análisis detallado por región", h2), Spacer(1, 0.3 * cm)]

    for region_name, rdata in region_data.items():
        region_flowables = [
            Paragraph(f"Región: {region_name}", h2),
            Spacer(1, 0.3 * cm),
            Paragraph(f"Longitud media de intercepto: {rdata.get('mean_um', '—')} µm", normal),
            Paragraph(f"Número ASTM G de la región: {rdata.get('astm', '—')}", normal),
            Spacer(1, 0.4 * cm),
        ]

        # Imagen de la región
        if rdata.get('imagen'):
            try:
                response = requests.get(rdata['imagen'], timeout=25)
                response.raise_for_status()
                img_data = BytesIO(response.content)
                pil_img = PILImage.open(img_data)
                w, h = pil_img.size
                aspect = w / h
                max_w = 15 * cm
                max_h = 9 * cm
                width = max_w
                height = width / aspect if (width / aspect) <= max_h else max_h
                width = height * aspect
                img_data.seek(0)
                img_region = Image(img_data, width=width, height=height)
                region_flowables.extend([
                    KeepTogether([img_region, Spacer(1, 0.2 * cm), Paragraph(f"Imagen – {region_name}", normal)]),
                    Spacer(1, 0.6 * cm)
                ])
            except Exception:
                region_flowables.append(Paragraph(f"⚠ No se pudo cargar la imagen de la región: {region_name}", normal))

        # ====================== HISTOGRAMA POR REGIÓN ======================
        region_dist = rdata.get('distribution_um', [])
        region_mean = rdata.get('mean_um')

        if len(region_dist) >= 2:
            try:
                hist_path = create_intercept_distribution_plot(
                    region_dist,
                    title=f"Distribución de longitud de intercepto - región {region_name}",
                    highlight_value=region_mean,
                    highlight_label=f"Media de la región = {region_mean:.2f} µm"
                )
                if hist_path and os.path.exists(hist_path):
                    img_hist = image_keep_aspect(hist_path, 14.5, 8.5)
                    region_flowables.extend([
                        KeepTogether([
                            img_hist,
                            Spacer(1, 0.2 * cm),
                            Paragraph(f"Figura 2. Distribución de longitud de intercepto - {region_name} (µm)", normal)
                        ]),
                        Spacer(1, 0.8 * cm)
                    ])
            except Exception as e:
                region_flowables.append(Paragraph(f"⚠ No se pudo generar el histograma de la región: {e}", normal))
        else:
            region_flowables.append(Paragraph("No hay suficientes datos de distribución para generar el histograma de la región.", normal))
            region_flowables.append(Spacer(1, 0.6 * cm))

        # Micrografías
        if rdata.get('micrografias'):
            micro_section = [Paragraph(f"Micrografías analizadas para la región: {region_name}", normal_bold), Spacer(1, 0.3 * cm)]
            for micro in rdata['micrografias']:
                try:
                    if micro.get('imagen'):
                        response = requests.get(micro['imagen'], timeout=25)
                        response.raise_for_status()
                        img_data = BytesIO(response.content)
                        pil_img = PILImage.open(img_data)
                        w, h = pil_img.size
                        aspect = w / h
                        max_w = 15 * cm; max_h = 9 * cm
                        width = max_w
                        height = width / aspect if (width / aspect) <= max_h else max_h
                        width = height * aspect
                        img_data.seek(0)
                        img_micro = Image(img_data, width=width, height=height)
                        caption = f"{micro['nombre']} — Original (Longitud media: {micro['mean_um']} µm)"
                        micro_section.extend([KeepTogether([img_micro, Spacer(1, 0.2 * cm), Paragraph(caption, normal)]), Spacer(1, 0.6 * cm)])

                    if micro.get('measure_imagen'):
                        response = requests.get(micro['measure_imagen'], timeout=25)
                        response.raise_for_status()
                        img_data = BytesIO(response.content)
                        pil_img = PILImage.open(img_data)
                        w, h = pil_img.size
                        aspect = w / h
                        max_w = 15 * cm; max_h = 9 * cm
                        width = max_w
                        height = width / aspect if (width / aspect) <= max_h else max_h
                        width = height * aspect
                        img_data.seek(0)
                        img_measure = Image(img_data, width=width, height=height)
                        micro_section.extend([KeepTogether([img_measure, Spacer(1, 0.2 * cm),
                                                           Paragraph(f"{micro['nombre']} — Imagen de medición / máscara", normal)]),
                                              Spacer(1, 0.7 * cm)])
                except Exception:
                    micro_section.append(Paragraph(f"⚠ No se pudo cargar la imagen: {micro.get('nombre')}", normal))
            region_flowables.append(KeepTogether(micro_section))

        detailed_section.extend(region_flowables)
        detailed_section.append(Spacer(1, 0.4 * cm))

    elements.append(KeepTogether(detailed_section))
    return elements