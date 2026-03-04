from rest_framework import serializers
from .models import Muestra, Region, Micrografia


class MicrografiaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Micrografia
        fields = "__all__"


class RegionSerializer(serializers.ModelSerializer):
    micrografias = MicrografiaSerializer(many=True, read_only=True)

    class Meta:
        model = Region
        fields = "__all__"


class MuestraSerializer(serializers.ModelSerializer):
    regiones = RegionSerializer(many=True, read_only=True)

    class Meta:
        model = Muestra
        fields = "__all__"