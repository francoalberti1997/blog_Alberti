import os
import tempfile
from collections import defaultdict, Counter

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from datetime import datetime
import requests

from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError, PermissionDenied

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
)

from PIL import Image as PILImage
from reportlab.platypus import Image
from reportlab.lib.units import cm

# Modelos y serializadores de tu app
from .models import GrainSize, Muestra, Region, Micrografia, Micrografia_mask, MicrographyMeasure
from .serializers import MuestraSerializer, RegionSerializer, MicrografiaSerializer

# Celery tasks
from .tasks import process_micrografia_mask, measure_grain_size

from rest_framework.exceptions import PermissionDenied
from celery import chain
import sys

from metalografia.utils.utils import get_um_by_px
from .models import Material

# =========================================================
# BASE VIEWSET (multi-tenant)
# =========================================================
class BaseCompanyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_company(self):
        user = self.request.user

        if not user.is_authenticated:
            raise PermissionDenied("Usuario no autenticado")

        if not hasattr(user, "member") or user.member.company is None:
            raise PermissionDenied("Usuario sin empresa")

        return user.member.company


# =========================================================
# MUESTRA
# =========================================================
class MuestraViewSet(BaseCompanyViewSet):
    serializer_class = MuestraSerializer
    permission_classes = [IsAuthenticated]


    def get_queryset(self):
        return Muestra.objects.filter(owner=self.get_company())

    def perform_create(self, serializer):
        serializer.save(owner=self.get_company())


# =========================================================
# REGION
# =========================================================
class RegionViewSet(BaseCompanyViewSet):
    serializer_class = RegionSerializer
    permission_classes = [IsAuthenticated]


    def get_queryset(self):
        return Region.objects.filter(muestra__owner=self.get_company())

    def perform_create(self, serializer):
        muestra = serializer.validated_data.get("muestra")

        if muestra.owner != self.get_company():
            raise PermissionDenied("No podés crear regiones en otra empresa")

        serializer.save()


# =========================================================
# MICROGRAFIA
# =========================================================
class MicrografiaViewSet(BaseCompanyViewSet):
    serializer_class = MicrografiaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        print(f"\n \n {self.request.user}\n \n")
        return Micrografia.objects.filter(
            region__muestra__owner=self.get_company()
        )
    
    def perform_create(self, serializer):
        print(self.request.data)
        region = serializer.validated_data.get("region")

        # ✅ validar que venga region
        if region is None:
            raise ValidationError({"region": "Este campo es obligatorio"})

        # ✅ validar ownership
        if region.muestra.owner != self.get_company():
            raise PermissionDenied("No podés crear micrografías en otra empresa")
    
        if 'um_by_px' in serializer.validated_data:
            del serializer.validated_data['um_by_px']

        # micrografia = serializer.save()

        # chain(
        #     process_micrografia_mask.s(micrografia.id),
        #     measure_grain_size.s()
        # ).apply_async()

        micrografia = serializer.save()

        # Ejecutamos la primera tarea y le "linkeamos" la segunda
        print("llamando Worker:")
        transaction.on_commit(
            lambda: process_micrografia_mask.apply_async(
                args=[micrografia.id],
                countdown=3,                    # 3 segundos de delay ayuda mucho
                link=measure_grain_size.s()
            )
        )

    def partial_update(self, request, *args, **kwargs):
        
        forbidden = {'imagen', 'region', 'id'}

        if set(request.data.keys()) & forbidden:
            return Response(
                {"error": "No se permite actualizar 'imagen' ni 'region'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = request.data.copy()  # clave

        um_by_px = data.get('um_by_px')

        obj_id = kwargs.get('pk')

        if um_by_px is not None:
            px = get_um_by_px(obj_id, um_by_px)

            if px is not None:
                try:
                    data['um_by_px'] = float(px)
                except (ValueError, TypeError):
                    return Response(
                        {"error": "um_by_px debe ser numérico"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        print(f"llega: {um_by_px}")
        request._full_data = data  # reemplaza internamente

        return super().partial_update(request, *args, **kwargs)


BASE_PREDICT_URL = "https://francoalb-magnesia.hf.space/segment"

class PredictView(APIView):

    def post(self, request, micrografia_id):
        # permission_classes = [IsAuthenticated]

        micrografia = get_object_or_404(Micrografia, id=micrografia_id)

        material = micrografia.region.muestra.material

        if not material or not material.has_model:
            return Response(
                {"error": "El material no tiene modelo asociado"},
                status=400
            )

        mask, created = Micrografia_mask.objects.get_or_create(
            micrografia=micrografia,
            defaults={
                "nombre": f"mask_{micrografia.nombre}",
                "status": "pending"
            }
        )

        if not created:
            if mask.status == "pending":
                return Response({
                    "status": "already_processing",
                    "mask_id": mask.id
                })
            else:
                return Response({
                    "status": "Mask already exists",
                    "mask_id": mask.id
                })
            
        # enviar tarea celery
        process_micrografia_mask.delay(mask.id)

        return Response({
            "status": "processing",
            "mask_id": mask.id
        })

class GrainMeasureView(APIView):
    def post(self, request, region_id):
        region = Region.objects.get(id=region_id)
        micrografias = region.micrografias.all()
        for i in micrografias:
            measure_grain_size(i)
        return Response({"message": "Midiendo tamaño de grano"})

class GetMask(APIView): 
    def get(self, request, micrografia_id):
        mask = get_object_or_404(Micrografia_mask, micrografia_id=micrografia_id)   
        if mask.status != "done" or not mask.imagen:
            return Response({"error": "Máscara no disponible"}, status=404) 
        url = mask.imagen.url
        relative_url = url.split("upload")[-1]
        relative_url = "/image/upload" + relative_url

        return Response({"mask_url": relative_url})


class MaterialView(APIView):
    def get(self, request):

        materials = Material.objects.all()        

        data = [
            {   "id": m.id,
                "nombre": m.nombre,
                "code": m.code,
                "has_model": m.has_model
            }
            for m in materials
        ]
        return Response({"materials": data})

# class MicrografiaMeasureView(APIView):
#     def get(self, request, micrografia_id):
#         micrografia = get_object_or_404(Micrografia, id=micrografia_id)
#         measure = micrografia.measure_micro
#         return Response({"mean_size": measure.mean_size, "standard_deviation": measure.standard_deviation})

# class RegionMeasureView(APIView):
#     def get(self, request, region_id):
#         region = get_object_or_404(Region, id=region_id)
#         grain_size = region.get_or_create_size()
#         mean_size, standard_deviation = grain_size.compute_from_micrograph_measures()
#         return Response({"mean_size": mean_size, "standard_deviation": standard_deviation})

# class MaskPhasesView(APIView):
#     def get(self, request, micrografia_id):
#         micrografia = get_object_or_404(Micrografia, id=micrografia_id)
#         try:
#             mask = micrografia.micrografias_mask
#             if mask.imagen and os.path.exists(mask.imagen.path):
#                 with open(mask.imagen.path, "rb") as f:
#                     return HttpResponse(f.read(), content_type="image/png")
#             else:
#                 return Response({"error": "Máscara no disponible"}, status=404)
#         except Micrografia_mask.DoesNotExist:
#             return Response({"error": "No se ha generado la máscara para esta micrografía"}, status=404)

