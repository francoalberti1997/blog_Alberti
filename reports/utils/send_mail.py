from django.core.mail import EmailMessage
from django.conf import settings
import os
import requests  # 👈 agregamos esto
from ..models import ReportPDF

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
        print("Enviando Mail (via servicio externo)")

        if os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as f:
                response = requests.post(
                    SERVER_MAIL,  # 👈 URL del otro server
                    data={
                        "subject": subject,
                        "body": body,
                        "to": pdf_obj.owner.user.email,
                    },
                    files={
                        "file": (os.path.basename(pdf_path), f, "application/pdf")
                    },
                    timeout=10
                )

            if response.status_code == 200:
                pdf_obj.status = "done"
                pdf_obj.save(update_fields=["status"])
                return 1

            print(f"Error response: {response.status_code} - {response.text}")
            return 0

        return 0

    except Exception as e:
        pdf_obj.status = "error"
        pdf_obj.save(update_fields=["status"])
        print(f"Error enviando email: {e}")
        return 0