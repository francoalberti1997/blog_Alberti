
from celery import shared_task
import requests
from django.core.files.base import ContentFile

from reports.utils.pdf.report_builder import build_full_report_pdf
from .models import Micrografia_mask
from algoritmos.tamaño_grano.astm_e112_test import generar_grilla_intercepciones_constantes
from django.core.mail import EmailMessage
from django.conf import settings
import os
from reports.models import ReportPDF
from .models import Region, Muestra, Micrografia, MicrographyMeasure
import traceback
from reports.utils.send_mail import send_report_email
from collections import defaultdict, Counter
import numpy as np
from datetime import datetime
import cloudinary                 
import cloudinary.uploader         

# ====================== IMPORTS PARA EL PDF ======================

BASE_PREDICT_URL = "https://francoalb-materialai.hf.space/segment/"
HF_TOKEN = os.getenv("HF_TOKEN")

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
            BASE_PREDICT_URL + micrografia.region.muestra.material.code + "/",
            headers=headers,
            files={"file": ("image.png", img_response.content, "image/png")},
            timeout=30
        )

        print("STATUS HF:", response.status_code)
        response.raise_for_status()

        result = response.content

        print("Subiendo máscara a Cloudinary...")
        upload_result = cloudinary.uploader.upload(
            result,
            folder="masks",
            public_id=f"mask_{micrografia.id}",
            overwrite=True,
            resource_type="image"
        )

        mask.imagen = upload_result['secure_url']
        mask.status = "done"
        mask.save()

        print(f"Máscara generada OK → micrografia {micrografia.id} | URL: {mask.imagen}")

    except Exception as e:
        print("ERROR en process_micrografia_mask:", str(e))
        mask.status = "error"
        mask.save(update_fields=['status'])
        raise

    return micrografia.id


@shared_task()
def measure_grain_size(micrografia):
    print("INICIANDO PROCESO DE MEDICIÓN")
    micrografia = Micrografia.objects.get(id=micrografia)

    if not micrografia.imagen:
        raise ValueError(f"La micrografía {micrografia} no tiene imagen cargada")

    img_file = micrografia.imagen.url

    if not hasattr(micrografia, 'micrografias_mask'):
        raise ValueError(f"No existe relación micrografias_mask en {micrografia}")

    mask_instance = micrografia.micrografias_mask
    if not mask_instance.imagen:
        raise ValueError(f"La máscara de {micrografia} no tiene archivo cargado")

    mask_file = mask_instance.imagen

    results = generar_grilla_intercepciones_constantes(
        img_file=img_file,
        mask_file=mask_file,
        safety_margin_px=5,
        num_rectas_objetivo=100,
    )

    micro_measure, _ = MicrographyMeasure.objects.update_or_create(
        micrografia=micrografia,
        defaults={
            "mean_size": results["mean_grain_size_um"],
            "standard_deviation": results["std_grain_size_um"],
            "is_valid": results["is_valid"],
            "distribution_quantiles": results["distribution_quantiles"],   
        }
    )


    if results["visualization_bytes"]:
        upload_result = cloudinary.uploader.upload(
            results["visualization_bytes"],
            folder="measurements",
            public_id=f"rectas_{micrografia.id}",
            overwrite=True,
            resource_type="image"
        )

        micro_measure.imagen = upload_result["secure_url"]
        micro_measure.save()


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


@shared_task
def generate_microstructural_report_pdf(pdf_id: int):

    print(f"Generando PDF ESQUELETO para ReportPDF id: {pdf_id}")

    pdf_obj = ReportPDF.objects.get(id=pdf_id)

    pdf_obj = ReportPDF.objects.select_related('muestra__material', 'owner__company').get(id=pdf_id)
    muestra = pdf_obj.muestra

    # === Cálculo de tamaños por región (siempre se ejecuta) ===
    for region in Region.objects.filter(muestra=muestra):
        grain_size = region.get_or_create_size()
        try:
            grain_size.compute_from_micrograph_measures()
        except Exception:
            pass

    from reports.utils.pdf.report_builder import build_full_report_pdf, build_pdf_data

    data = build_pdf_data(pdf_obj)

    print("Data para PDF construida:", data)

    pdf_bytes, filename = build_full_report_pdf(data)

    pdf_obj.file.save(filename, ContentFile(pdf_bytes), save=False)
    pdf_obj.save()

    send_report_email(pdf_id=pdf_obj.id)

    print(f"✅ PDF generado → {filename}")
    return 1