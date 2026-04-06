from celery import shared_task
import requests
from django.core.files.base import ContentFile
from .models import Micrografia_mask
from algoritmos.tamaño_grano.astm_e112_test import generar_grilla_intercepciones_constantes
from django.core.mail import EmailMessage
from django.conf import settings
import os
from reports.models import ReportPDF
from .utils.pdf_builder import *
from metalografia.utils.utils import *
from .models import Region, Muestra, Micrografia, MicrographyMeasure
from django.core.files.base import ContentFile
from django.conf import settings
import traceback
from reports.utils.send_mail import send_report_email


BASE_PREDICT_URL = "https://francoalb-materialai.hf.space/segment/"

HF_TOKEN = os.getenv("HF_TOKEN")

import cloudinary.uploader
from celery import shared_task
from django.core.files.base import ContentFile  # ya no es necesario, pero lo dejamos por si acaso

@shared_task
def process_micrografia_mask(mask_id):
    micrografia = Micrografia.objects.get(id=mask_id)

    mask = Micrografia_mask.objects.create(
        micrografia=micrografia,
        nombre=micrografia.nombre + "_mask",
        status="processing"
    )

    try:
        print("Descargando imagen desde Cloudinary...")
        image_url = micrografia.imagen.url

        img_response = requests.get(image_url, timeout=15)
        img_response.raise_for_status()
        print("Imagen descargada OK")

        headers = {
            "Authorization": f"Bearer {os.getenv('HF_TOKEN')}"
        }

        print("Enviando imagen a Hugging Face...")
        response = requests.post(
            BASE_PREDICT_URL + micrografia.region.muestra.material.code + "/",  # endpoint dinámico por material
            headers=headers,
            files={
                "file": ("image.png", img_response.content, "image/png")
            },
            timeout=30
        )

        print("STATUS HF:", response.status_code)
        response.raise_for_status()

        result = response.content  # bytes de la máscara

        # ====================== SUBIDA A CLOUDINARY ======================
        print("Subiendo máscara a Cloudinary...")

        upload_result = cloudinary.uploader.upload(
            result,                                   # acepta bytes directamente
            folder="masks",                           # carpeta opcional
            public_id=f"mask_{micrografia.id}",       # nombre único
            overwrite=True,
            resource_type="image"
        )

        # Asignamos la URL segura que devuelve Cloudinary
        mask.imagen = upload_result['secure_url']     # o upload_result['public_id'] según tu config

        mask.status = "done"
        mask.save()

        print(f"Máscara generada OK → micrografia {micrografia.id} | URL: {mask.imagen}")

    except Exception as e:
        print("ERROR en process_micrografia_mask:", str(e))
        
        mask.status = "error"
        mask.save(update_fields=['status'])
        raise

    print(f"Retornando id de micrografia: {micrografia.id}")
    return micrografia.id

@shared_task()
def measure_grain_size(micrografia):
    """
    Genera grilla de intercepciones usando la imagen y máscara REALES del objeto Micrografia.
    """
    # 1. Imagen original

    print("INICIANDO PROCESO DE MEDICIÓN")

    micrografia = Micrografia.objects.get(id=micrografia)

    if not micrografia.imagen:
        raise ValueError(f"La micrografía {micrografia} no tiene imagen cargada")

    img_file = micrografia.imagen.url

    # 2. Máscara (OneToOne)
    if not hasattr(micrografia, 'micrografias_mask'):
        raise ValueError(f"No existe relación micrografias_mask en {micrografia}")

    mask_instance = micrografia.micrografias_mask

    if not mask_instance.imagen:
        raise ValueError(f"La máscara de {micrografia} no tiene archivo cargado")

    mask_file = mask_instance.imagen

    # 4. Llamada (exactamente como la tenías, pero con rutas dinámicas)
    results = generar_grilla_intercepciones_constantes(
        img_file            = img_file,
        mask_file           = mask_file,
        # output_dir          = output_dir,
        safety_margin_px    = 5,
        num_rectas_objetivo = 100,
    )
    

    micro_measure, _ = MicrographyMeasure.objects.update_or_create(
        micrografia=micrografia,
        defaults={
            "mean_size": results["mean_grain_size_um"],
            "standard_deviation": results["std_grain_size_um"],
            "is_valid": results["is_valid"],
        }
    )

    validity = results["is_valid"]
    print(f"Validity: {validity}")

    if validity is False:
        micro_measure.is_valid = False
        micro_measure.save()
        return 1
    
    micro_measure.mean_size = results["mean_grain_size_um"]
    micro_measure.standard_deviation = results["std_grain_size_um"]
    micro_measure.is_valid = validity

    micro_measure.save()
    
    return 1

from collections import defaultdict, Counter
import numpy as np
import os
from celery import shared_task
from django.core.files.base import ContentFile

@shared_task
def generate_microstructural_report_pdf(pdf_id: int):
    print(f"Generando PDF para ReportPDF id: {pdf_id}")
    pdf_obj = ReportPDF.objects.select_related('muestra__material', 'owner__company').get(id=pdf_id)
    muestra = pdf_obj.muestra

    # === Cálculo de tamaños por región ===
    for region in Region.objects.filter(muestra=muestra):
        grain_size = region.get_or_create_size()
        try:
            grain_size.compute_from_micrograph_measures()
        except Exception:
            pass

    # === Datos básicos ===
    operador_nombre = f"{pdf_obj.owner.name} {pdf_obj.owner.surname}"
    institucion = pdf_obj.owner.company.name if pdf_obj.owner.company else ""
    logo_url = pdf_obj.owner.company.image.url if pdf_obj.owner.company and pdf_obj.owner.company.image else None

    from datetime import datetime
    now = datetime.now()
    MESES_ES = [None, 'enero','febrero','marzo','abril','mayo','junio',
                'julio','agosto','septiembre','octubre','noviembre','diciembre']
    fecha_actual = f"{now.day} de {MESES_ES[now.month]} de {now.year}"

    # === Recolectar todos los granos con medida ===
    grain_data = []
    invalid_micrographs = []
    for region in Region.objects.filter(muestra=muestra):
        for micro in region.micrografias.all():
            """
            Filtrar por aquellas micrografías con measure_micro. MOSTRAR LAS QUE NO SE CONSIDERAN IGUAL PERO NO MEDIDAS.
            """
            try:
                measure = micro.measure_micro  
                if measure.mean_size is None or micro.um_by_px is None or (measure.is_valid is False):
                    print(f"No será tenida en cuenta la micrografía: {micro.nombre}")
                    invalid_micrographs.append({
                        "nombre": micro.nombre,
                    "path": micro.imagen.url if micro.imagen else None,
                    })
                    
                    continue

                tc_um, _ = measure.convert_from_px_to_um()
                calidad = assign_calidad(tc_um)
                tipo = assign_tipo(tc_um)

                grain_data.append({
                    'tc_um': tc_um,
                    'micro': micro,
                    'region': region,
                    'calidad': calidad,
                    'tipo': tipo,
                })
            except Exception as e:
                continue  # silencioso para no romper todo

    if not grain_data:
        pdf_obj.status = "error_no_data"
        pdf_obj.save()
        return 0

    # === Estadísticas generales ===
    values = np.array([g['tc_um'] for g in grain_data])
    n_grains = len(values)

    sinter_grains = [g for g in grain_data if g['tipo'] == "sinterizado"]
    electro_grains = [g for g in grain_data if g['tipo'] == "electrofundido"]

    sinter_pct = len(sinter_grains) / n_grains * 100 if n_grains else 0
    electro_pct = 100 - sinter_pct

    count_by_cal = Counter(g['calidad']['label'] for g in grain_data)

    # Tabla de calidades
    calidad_table_data = [["Calidad", "Rango (µm)", "Cantidad", "Porcentaje"]]
    for cal in sorted(CALIDADES_FIJAS, key=lambda c: c["id"]):
        lbl = cal["label"]
        cnt = count_by_cal[lbl]
        pct = cnt / n_grains * 100 if n_grains else 0
        rango_str = f"{cal['min']}–{cal['max'] if cal['max'] < 99999 else '>900'}"
        calidad_table_data.append([lbl, rango_str, cnt, f"{pct:.1f}%"])

    dominant_label = count_by_cal.most_common(1)[0][0] if count_by_cal else "—"
    n_calidades_encontradas = len(count_by_cal)

    dist_plot_path = create_distribution_plot(values)

    # === Preparar datos de regiones + imágenes ===
    # regions_data = []

    # for region in Region.objects.filter(muestra=muestra):
    #     reg_dict = {
    #         'nombre': region.nombre,
    #         'titulo': f"Región: {region.nombre}",
    #         'imagen_path': region.imagen.url if region.imagen else None,
    #         'calidades': []
    #     }

    #     # Tamaño medio de la región
    #     try:
    #         if hasattr(region, 'region_measure') and region.region_measure.mean_size is not None:
    #             reg_dict['titulo'] += f" – Tamaño medio: {region.region_measure.mean_size:.1f} µm"
    #     except:
    #         pass

    #     # Agrupar micrografías de esta región por calidad
    #     region_grains = [g for g in grain_data if g['region'].id == region.id]
    #     region_by_cal = defaultdict(list)
    #     for g in region_grains:
    #         region_by_cal[g['calidad']['id']].append(g)

    #     for cal_id in sorted(region_by_cal.keys()):
    #         cal = next(c for c in CALIDADES_FIJAS if c["id"] == cal_id)

    #         cal_block = {
    #             'id': cal_id,
    #             'label': cal['label'],
    #             'figuras': []
    #         }

    #         for grain in region_by_cal[cal_id]:
    #             micro = grain['micro']
    #             if micro.imagen and os.path.exists(micro.imagen.url):
    #                 cal_block['figuras'].append({
    #                     'path': micro.imagen.url,
    #                     'caption': f"{micro.nombre} – {cal['label']} – Región {region.nombre}"
    #                 })

    #         if cal_block['figuras']:
    #             reg_dict['calidades'].append(cal_block)

    #     regions_data.append(reg_dict)

    from collections import defaultdict

    regions_data = []

    for region in Region.objects.filter(muestra=muestra):
        reg_dict = {
            'nombre': region.nombre,
            'titulo': f"Región: {region.nombre}",
            'imagen_path': getattr(region.imagen, 'url', None) if region.imagen else None,
            'calidades': []
        }

        # Tamaño medio de la región
        try:
            if hasattr(region, 'region_measure') and region.region_measure.mean_size is not None:
                reg_dict['titulo'] += f" – Tamaño medio: {region.region_measure.mean_size:.1f} µm"
        except:
            pass

        # Agrupar micrografías de esta región por calidad
        region_grains = [g for g in grain_data if g['region'].id == region.id]
        region_by_cal = defaultdict(list)
        for g in region_grains:
            region_by_cal[g['calidad']['id']].append(g)

        for cal_id in sorted(region_by_cal.keys()):
            cal = next((c for c in CALIDADES_FIJAS if c["id"] == cal_id), None)
            if not cal:
                continue

            cal_block = {
                'id': cal_id,
                'label': cal['label'],
                'figuras': []
            }

            for grain in region_by_cal[cal_id]:
                micro = grain['micro']
                
                # ✅ CORRECCIÓN: NO usar os.path.exists() con Cloudinary
                image_url = getattr(micro.imagen, 'url', None) if micro.imagen else None
                
                if image_url:
                    cal_block['figuras'].append({
                        'path': image_url,   # URL de Cloudinary
                        'caption': f"{micro.nombre} – {cal['label']} – Región {region.nombre}"
                    })

            # Solo agregar el bloque de calidad si tiene al menos una figura
            if cal_block['figuras']:
                reg_dict['calidades'].append(cal_block)

        regions_data.append(reg_dict)

    # Debug: ver qué se está generando
    print(f"Regiones generadas: {len(regions_data)}")
    for r in regions_data:
        print(f"  - {r['nombre']}: {len(r['calidades'])} calidades")
        for c in r['calidades']:
            print(f"    → Calidad {c['id']}: {len(c['figuras'])} figuras")

    # === Diccionario para el PDF ===
    data = {
        'muestra_id': muestra.id,
        'material_name': muestra.material.nombre if muestra.material else "Material no especificado",
        'muestra_nombre': muestra.nombre,
        'fecha_actual': fecha_actual,
        'operador_nombre': operador_nombre,
        'institucion': institucion,
        'n_grains': n_grains,
        'len_sinter': len(sinter_grains),
        'len_electro': len(electro_grains),
        'sinter_pct': sinter_pct,
        'electro_pct': electro_pct,
        'dominant_label': dominant_label,
        'n_calidades': n_calidades_encontradas,
        'calidad_table_data': calidad_table_data,
        'dist_plot_path': dist_plot_path,
        # 'muestra_imagen_path': muestra.imagen.url if getattr(muestra, 'imagen', None) and os.path.exists(muestra.imagen.url) else None,
        'muestra_imagen_path': muestra.imagen.url if hasattr(muestra.imagen, 'url') else None,        
        'regions': regions_data,
        "logo_url": logo_url,
        "invalid_micrographs": invalid_micrographs
    }

    # === Generar PDF ===
    pdf_bytes, filename = build_pdf_content(data)

    pdf_obj.file.save(filename, ContentFile(pdf_bytes), save=False)
    # pdf_obj.status = "done"
    pdf_obj.save()
    print("Enviando reporte al server remoto")
    send_report_email(pdf_id=pdf_obj.id)
    return 1
