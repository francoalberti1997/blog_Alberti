from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView
from metalografia.tasks import generate_microstructural_report_pdf
from reports.models import ReportPDF
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from metalografia.models import Muestra, Micrografia
from .models import ReportPDF
from django.shortcuts import get_object_or_404
from .models import ReportPDF
from .serializers import ReportPDFSerializer
from rest_framework import status
from django.db import models

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

        if muestra.owner != company:
            raise PermissionDenied("No tenés acceso a esta muestra")

        if not muestra.muestra.exists():   # related_name="muestra" en el modelo Region
            return Response({
                "error": "La muestra no tiene regiones",
                "detalle": "Debes crear al menos una región antes de generar el PDF."
            }, status=status.HTTP_400_BAD_REQUEST)

        # ================================================
        # 2. Validar que todas las regiones tengan al menos una micrografía
        # ================================================
        regiones_sin_micrografias = muestra.muestra.annotate(
            num_micrografias=models.Count('micrografias')
        ).filter(num_micrografias=0)

        if regiones_sin_micrografias.exists():
            regiones_faltantes = [
                {
                    "region_id": region.id,
                    "region_nombre": region.nombre,
                    "muestra_nombre": muestra.nombre
                }
                for region in regiones_sin_micrografias
            ]

            return Response({
                "error": "Algunas regiones no tienen micrografías",
                "detalle": "Todas las regiones deben tener al menos una micrografía para generar el PDF.",
                "regiones_sin_micrografias": regiones_faltantes
            }, status=status.HTTP_400_BAD_REQUEST)

        micrografias_sin_um = Micrografia.objects.filter(
            region__muestra=muestra,
            um_by_px__isnull=True
        ).select_related('region', 'region__muestra')

        if micrografias_sin_um.exists():
            faltantes = []
            for micro in micrografias_sin_um:
                faltantes.append({
                    "micrografia_id": micro.id,
                    "micrografia_nombre": micro.nombre,
                    "region_nombre": micro.region.nombre,
                    "muestra_nombre": micro.region.muestra.nombre,
                    "muestra_id": micro.region.muestra.id
                })

            
            return Response({
                "error": "Faltan calibraciones (um_by_px) en algunas micrografías",
                "detalle": "No se puede generar el PDF porque las siguientes micrografías no tienen definido um_by_px",
                "micrografias_faltantes": faltantes
            }, status=status.HTTP_400_BAD_REQUEST)


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
    permission_classes = [IsAuthenticated]

    def get(self, request, id=None):
        user = request.user

        # Caso 1: viene ID → uno solo
        if id:
            pdf_obj = get_object_or_404(ReportPDF, id=id, owner__user=user)
            serializer = ReportPDFSerializer(pdf_obj)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Caso 2: no viene ID → todos del usuario
        pdfs = ReportPDF.objects.filter(owner__user=request.user)
        serializer = ReportPDFSerializer(pdfs, many=True)
        

        return Response(serializer.data, status=status.HTTP_200_OK)