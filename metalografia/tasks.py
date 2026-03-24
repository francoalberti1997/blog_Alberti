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
from celery import shared_task
from django.core.files.base import ContentFile
from django.conf import settings
import traceback
from reports.utils.send_mail import send_report_email


BASE_PREDICT_URL = "https://francoalb-magnesia.hf.space/segment/45956/"

HF_TOKEN = os.getenv("HF_TOKEN")

@shared_task
def process_micrografia_mask(mask_id):

    micrografia = Micrografia.objects.get(id=mask_id)

    mask = Micrografia_mask.objects.create(
        micrografia = micrografia,
        nombre = micrografia.nombre + "_mask"
    )

    try:

        with micrografia.imagen.open("rb") as img_file:

            headers = {
                "Authorization": f"Bearer {HF_TOKEN}"
            }

            response = requests.post(
                BASE_PREDICT_URL,
                headers=headers,
                files={"file": img_file}
            )

        response.raise_for_status()

        result = response.content  # suponiendo que devuelve la máscara

        mask.imagen.save(
            f"mask_{micrografia.id}.png",
            ContentFile(result),
            save=False
        )

        mask.status = "done"
        mask.save()

    except Exception as e:

        mask.status = "error"
        mask.save()

        raise e

    return micrografia.id

@shared_task()
def measure_grain_size(micrografia):
    """
    Genera grilla de intercepciones usando la imagen y máscara REALES del objeto Micrografia.
    """
    # 1. Imagen original

    micrografia = Micrografia.objects.get(id=micrografia)

    if not micrografia.imagen:
        raise ValueError(f"La micrografía {micrografia} no tiene imagen cargada")

    img_file = micrografia.imagen.path

    # 2. Máscara (OneToOne)
    if not hasattr(micrografia, 'micrografias_mask'):
        raise ValueError(f"No existe relación micrografias_mask en {micrografia}")

    mask_instance = micrografia.micrografias_mask

    if not mask_instance.imagen:
        raise ValueError(f"La máscara de {micrografia} no tiene archivo cargado")

    mask_file = mask_instance.imagen

    # 3. Carpeta de salida (puedes cambiar el criterio)
    output_dir = f"results_v4_constante/micro_{micrografia.id:04d}"

    # 4. Llamada (exactamente como la tenías, pero con rutas dinámicas)
    results = generar_grilla_intercepciones_constantes(
        img_file            = img_file,
        mask_file           = mask_file,
        output_dir          = output_dir,
        safety_margin_px    = 5,
        num_rectas_objetivo = 100,
    )
    

    micro_measure = MicrographyMeasure.objects.create(
        micrografia = micrografia
    )
    micro_measure.mean_size = results["mean_grain_size_um"]
    micro_measure.standard_deviation = results["std_grain_size_um"]

    micro_measure.save()
    
    return 1


# @shared_task(bind=True, max_retries=3)
# def generate_microstructural_report_pdf(self, pdf_id: int):
#     try:
#         pdf_obj = ReportPDF.objects.select_related('muestra__material', 'owner__company').get(id=pdf_id)
#         muestra = pdf_obj.muestra
#         muestra_id = muestra.id

#         pdf_obj.status = "processing"
#         pdf_obj.save()

#         region_qs = Region.objects.filter(muestra=muestra_id)

#         for r in region_qs:
#             grain_size = r.get_or_create_size()
#             try:
#                 grain_size.compute_from_micrograph_measures()
#             except Exception:
#                 pass

#         operador_nombre = pdf_obj.owner.name + " " + pdf_obj.owner.surname
#         company = pdf_obj.owner.company
#         institucion = company.name
#         logo_url = company.image.path if company.image else None

#         # -------- resto de tu lógica SIN CAMBIOS --------

#         data = { 'muestra_id': muestra_id, 'material_name': muestra.material.nombre if muestra.material else "Material no especificado", 'muestra_nombre': muestra.nombre, 'fecha_actual': fecha_actual, 'operador_nombre': operador_nombre, 'institucion': institucion, 'n_grains': n_grains, 'len_sinter': len(sinter_grains), 'len_electro': len(electro_grains), 'sinter_pct': sinter_pct, 'electro_pct': electro_pct, 'dominant_label': dominant_label, 'n_calidades': n_calidades_encontradas, 'calidad_table_data': calidad_table_data, 'dist_plot_path': dist_plot_path, 'muestra_imagen_path': muestra.imagen.path if muestra.imagen and os.path.exists(muestra.imagen.path) else None, 'regions': regions_data, "logo_url":logo_url }


#         pdf_bytes, filename = build_pdf_content(data)

#         pdf_obj.file.save(filename, ContentFile(pdf_bytes), save=False)
#         pdf_obj.status = "done"
#         pdf_obj.save()

#         # CLAVE: disparar mail
#         send_mail.delay(pdf_obj.id)

#         return {"status": "ok", "pdf_id": pdf_obj.id}

#     except Exception as exc:
#         pdf_obj.status = "error"
#         pdf_obj.save()

#         raise self.retry(exc=exc, countdown=60)

# @shared_task
# def generate_microstructural_report_pdf(pdf_id: int):
#     pdf_obj = ReportPDF.objects.select_related('muestra__material').get(id=pdf_id)
#     muestra = pdf_obj.muestra
#     muestra_id = muestra.id

#     region = Region.objects.filter(muestra=muestra_id)

#     for r in region:
#         grain_size = r.get_or_create_size()
#         grain_size.compute_from_micrograph_measures()

#     # Campos que pueden venir del modelo o del request
#     operador_nombre = pdf_obj.owner.name + " " + pdf_obj.owner.surname
#     company = pdf_obj.owner.company
#     institucion = company.name
#     logo_url = company.image.path if company.image else None


#     # Fecha
#     from datetime import datetime
#     now = datetime.now()
#     MESES_ES = [
#         None, 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
#         'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
#     ]
#     fecha_actual = f"{now.day} de {MESES_ES[now.month]} de {now.year}"

#     # Recolectar datos
#     grain_data = []
#     print("Ingresando Loop")
#     for region in muestra.muestra.all():
#         for micro in region.micrografias.all():
#             try:
#                 measure = micro.measure_micro
#                 print(f"measure: {measure}")

#                 print(f"mean_size: {measure.mean_size}")
#                 print("\n")
#                 print(f"um_by_px: { micro.um_by_px}")
#                 print("\n")
                
#                 if measure.mean_size and micro.um_by_px:    
#                     print("Ingresó")
#                     tc_um, _ = measure.convert_from_px_to_um()
#                     calidad = assign_calidad(tc_um)
#                     tipo = assign_tipo(tc_um)

#                     grain_data.append({
#                         'tc_um': tc_um,
#                         'micro': micro,
#                         'region': region,
#                         'calidad': calidad,
#                         'tipo': tipo,
#                     })
#             except Exception:
#                 continue

#     if not grain_data:
#         pdf_obj.status = "error_no_data"
#         pdf_obj.save()
#         return 0

#     values = np.array([g['tc_um'] for g in grain_data])
#     n_grains = len(values)

#     sinter_grains = [g for g in grain_data if g['tipo'] == "sinterizado"]
#     electro_grains = [g for g in grain_data if g['tipo'] == "electrofundido"]

#     sinter_pct = len(sinter_grains) / n_grains * 100 if n_grains else 0
#     electro_pct = 100 - sinter_pct

#     count_by_cal = Counter(g['calidad']['label'] for g in grain_data)

#     calidad_table_data = [["Calidad", "Rango (µm)", "Cantidad", "Porcentaje"]]

#     for cal in sorted(CALIDADES_FIJAS, key=lambda c: c["id"]):
#         lbl = cal["label"]
#         cnt = count_by_cal[lbl]
#         pct = cnt / n_grains * 100 if n_grains else 0

#         rango_str = f"{cal['min']}–{cal['max'] if cal['max'] < 99999 else '>900'}"

#         calidad_table_data.append([lbl, rango_str, cnt, f"{pct:.1f}%"])

#     dominant_label = count_by_cal.most_common(1)[0][0] if count_by_cal else "—"
#     n_calidades_encontradas = len(count_by_cal)

#     dist_plot_path = create_distribution_plot(values)

#     # Preparar datos de regiones
#     regions_data = []
#     fig_num = 3

#     for region in muestra.muestra.all():
#         reg_dict = {
#             'nombre': region.nombre,
#             'titulo': f"Región: {region.nombre}",
#             'imagen_path': region.imagen.path if region.imagen and os.path.exists(region.imagen.path) else None,
#             'calidades': []
#         }

#         # Agregar tamaño medio si existe
#         try:
#             if hasattr(region, 'region_measure') and region.region_measure.mean_size is not None:
#                 reg_dict['titulo'] += f" – Tamaño medio: {region.region_measure.mean_size:.1f} µm"
#         except Exception:
#             pass

#         region_grains = [g for g in grain_data if g['region'].id == region.id]
#         region_by_cal = defaultdict(list)

#         for g in region_grains:
#             region_by_cal[g['calidad']['id']].append(g)

#         for cal_id in sorted(region_by_cal.keys()):
#             cal = next(c for c in CALIDADES_FIJAS if c["id"] == cal_id)

#             cal_block = {
#                 'id': cal_id,
#                 'label': cal['label'],
#                 'figuras': []
#             }

#             for grain in region_by_cal[cal_id]:
#                 micro = grain['micro']

#                 if micro.imagen and os.path.exists(micro.imagen.path):
#                     cal_block['figuras'].append({
#                         'path': micro.imagen.path,
#                         'caption': f"{micro.nombre} – {cal['label']} – Región {region.nombre}"
#                     })
#                     fig_num += 1

#             if cal_block['figuras']:
#                 reg_dict['calidades'].append(cal_block)

#         regions_data.append(reg_dict)

#     # Diccionario final
#     data = {
#         'muestra_id': muestra_id,
#         'material_name': muestra.material.nombre if muestra.material else "Material no especificado",
#         'muestra_nombre': muestra.nombre,
#         'fecha_actual': fecha_actual,
#         'operador_nombre': operador_nombre,
#         'institucion': institucion,
#         'n_grains': n_grains,
#         'len_sinter': len(sinter_grains),
#         'len_electro': len(electro_grains),
#         'sinter_pct': sinter_pct,
#         'electro_pct': electro_pct,
#         'dominant_label': dominant_label,
#         'n_calidades': n_calidades_encontradas,
#         'calidad_table_data': calidad_table_data,
#         'dist_plot_path': dist_plot_path,
#         'muestra_imagen_path': muestra.imagen.path if muestra.imagen and os.path.exists(muestra.imagen.path) else None,
#         'regions': regions_data,
#         "logo_url": logo_url
#     }

#     # Generar PDF
#     pdf_bytes, filename = build_pdf_content(data)

#     content = ContentFile(pdf_bytes)

#     pdf_obj.file.save(filename, content, save=False)

#     pdf_obj.status = "done"
#     pdf_obj.save()

#     send_report_email(pdf_id=pdf_obj.id)
#     return 1


from collections import defaultdict, Counter
import numpy as np
import os
from celery import shared_task
from django.core.files.base import ContentFile

@shared_task
def generate_microstructural_report_pdf(pdf_id: int):
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
    logo_url = pdf_obj.owner.company.image.path if pdf_obj.owner.company and pdf_obj.owner.company.image else None

    from datetime import datetime
    now = datetime.now()
    MESES_ES = [None, 'enero','febrero','marzo','abril','mayo','junio',
                'julio','agosto','septiembre','octubre','noviembre','diciembre']
    fecha_actual = f"{now.day} de {MESES_ES[now.month]} de {now.year}"

    # === Recolectar todos los granos con medida ===
    grain_data = []
    for region in Region.objects.filter(muestra=muestra):
        for micro in region.micrografias.all():
            try:
                measure = micro.measure_micro  # asumo que es el related_name correcto
                if measure.mean_size is None or micro.um_by_px is None:
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
    regions_data = []

    for region in Region.objects.filter(muestra=muestra):
        reg_dict = {
            'nombre': region.nombre,
            'titulo': f"Región: {region.nombre}",
            'imagen_path': region.imagen.path if region.imagen and os.path.exists(region.imagen.path) else None,
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
            cal = next(c for c in CALIDADES_FIJAS if c["id"] == cal_id)

            cal_block = {
                'id': cal_id,
                'label': cal['label'],
                'figuras': []
            }

            for grain in region_by_cal[cal_id]:
                micro = grain['micro']
                if micro.imagen and os.path.exists(micro.imagen.path):
                    cal_block['figuras'].append({
                        'path': micro.imagen.path,
                        'caption': f"{micro.nombre} – {cal['label']} – Región {region.nombre}"
                    })

            if cal_block['figuras']:
                reg_dict['calidades'].append(cal_block)

        regions_data.append(reg_dict)

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
        'muestra_imagen_path': muestra.imagen.path if getattr(muestra, 'imagen', None) and os.path.exists(muestra.imagen.path) else None,
        'regions': regions_data,
        "logo_url": logo_url
    }

    # === Generar PDF ===
    pdf_bytes, filename = build_pdf_content(data)

    pdf_obj.file.save(filename, ContentFile(pdf_bytes), save=False)
    pdf_obj.status = "done"
    pdf_obj.save()

    send_report_email(pdf_id=pdf_obj.id)
    return 1