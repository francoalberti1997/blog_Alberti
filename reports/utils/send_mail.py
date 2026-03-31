from django.core.mail import EmailMessage
from django.conf import settings
import os
from ..models import ReportPDF
import requests
from requests.exceptions import Timeout, ConnectionError, RequestException

SERVER_MAIL = "https://francoalberti97.pythonanywhere.com/send/"  # 👈 URL del otro server

def send_report_email(pdf_id: int):
    pdf_obj = ReportPDF.objects.select_related('owner').get(id=pdf_id)

    if not pdf_obj.file:
        return 0

    subject = "Informe microestructural"
    body = f"""
    
    Estimado/a {pdf_obj.owner.name},

    Adjuntamos el informe microestructural correspondiente a su solicitud.
    El código de este documento para seguimiento es: {pdf_obj.value}. 
    Ante cualquier consulta, observación o devolución, no dude en responder a este mismo correo. 
    Su opinión es muy importante para nosotros. 
    Quedamos a su disposición.
    Atentamente,
    Franco Alberti

    """

    pdf_path = pdf_obj.file.path


    try:
        print("Enviando Mail (via servicio externo)...")

        if not os.path.exists(pdf_path):
            print(f"PDF no encontrado en: {pdf_path}")
            pdf_obj.status = "error"
            pdf_obj.save(update_fields=["status"])
            return 0

        filename = os.path.basename(pdf_path)
        file_size_kb = os.path.getsize(pdf_path) / 1024

        print(f"Enviando archivo: {filename} ({file_size_kb:.1f} KB)")

        with open(pdf_path, 'rb') as f:
            response = requests.post(
                SERVER_MAIL,
                data={
                    "subject": subject,
                    "body": body,
                    "to": pdf_obj.owner.user.email,
                },
                files={
                    "file": (filename, f, "application/pdf")
                },
                timeout=(15, 90),      # ← (connect timeout, read/write timeout)
                # stream=True no es necesario aquí pero puedes probar
            )

        if response.status_code == 200:
            print("✅ Email enviado correctamente")
            pdf_obj.status = "done"
            pdf_obj.save(update_fields=["status"])
            return 1
        else:
            print(f"❌ Error del servidor de mail: {response.status_code} - {response.text[:400]}")
            pdf_obj.status = "error"
            pdf_obj.save(update_fields=["status"])
            return 0

    except Timeout as e:
        print(f"⏰ Timeout al enviar el email (probablemente el servidor es lento): {e}")
        pdf_obj.status = "error"
        pdf_obj.save(update_fields=["status"])
        return 0

    except (ConnectionError, RequestException) as e:
        print(f"❌ Error de conexión/red: {e}")
        pdf_obj.status = "error"
        pdf_obj.save(update_fields=["status"])
        return 0

    except Exception as e:
        print(f"❌ Error inesperado enviando email: {type(e).__name__}: {e}")
        pdf_obj.status = "error"
        pdf_obj.save(update_fields=["status"])
        return 0