from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView
from metalografia.tasks import generate_microstructural_report_pdf
from reports.models import ReportPDF
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from metalografia.models import Muestra
from .models import ReportPDF
from django.shortcuts import get_object_or_404
from .models import ReportPDF
from .serializers import ReportPDFSerializer
from rest_framework import status


class GeneratePDF(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        muestra_id = request.data.get("muestra_id")

        if not muestra_id:
            raise ValidationError({"muestra_id": "Este campo es obligatorio"})

        try:
            muestra = Muestra.objects.get(id=muestra_id)
        except Muestra.DoesNotExist:
            raise ValidationError({"muestra_id": "No existe esa muestra"})

        company = request.user.member.company

        # 🔐 VALIDACIÓN CLAVE
        if muestra.owner != company:
            raise PermissionDenied("No tenés acceso a esta muestra")

        pdf_obj = ReportPDF.objects.create(
            owner=request.user.member,
            muestra=muestra
        )        
        # Celery (opcional)(
        generate_microstructural_report_pdf.delay(pdf_obj.id)

        return Response({
            "message": f"Generando reporte. Te enviaremos un mail cuando esté listo. Tu id de seguimiento es: {pdf_obj.id}",
        })

class TrackPDF(APIView):
    def get(self, request, id):
        pdf_obj = get_object_or_404(ReportPDF, id=id)

        serializer = ReportPDFSerializer(pdf_obj)

        return Response(serializer.data, status=status.HTTP_200_OK)