from django.core.mail import EmailMessage
from django.conf import settings
import os
from ..models import ReportPDF


def send_report_email(pdf_id: int):
    pdf_obj = ReportPDF.objects.select_related('owner').get(id=pdf_id)

    if not pdf_obj.file:
        return 0

    subject = "Informe microestructural"
    body = f"""
    
    Estimado/a {pdf_obj.owner.name},

    Adjuntamos el informe microestructural correspondiente a su solicitud.

    El código de este documento para seguimiento es: {pdf_obj.value}

    Ante cualquier consulta, observación o devolución, no dude en responder a este mismo correo. Su feedback es importante para nosotros.

    Quedamos a su disposición.

    Atentamente,
    Franco Alberti

    """
    email = EmailMessage(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [pdf_obj.owner.user.email],
    )

    # adjuntar PDF
    pdf_path = pdf_obj.file.path
    if os.path.exists(pdf_path):
        with open(pdf_path, 'rb') as f:
            email.attach(os.path.basename(pdf_path), f.read(), 'application/pdf')

    email.send()
    return 1