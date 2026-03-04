from rest_framework import viewsets
from .models import Muestra, Region, Micrografia
from .serializers import MuestraSerializer, RegionSerializer, MicrografiaSerializer


class MuestraViewSet(viewsets.ModelViewSet):
    queryset = Muestra.objects.all()
    serializer_class = MuestraSerializer


class RegionViewSet(viewsets.ModelViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionSerializer


class MicrografiaViewSet(viewsets.ModelViewSet):
    queryset = Micrografia.objects.all()
    serializer_class = MicrografiaSerializer