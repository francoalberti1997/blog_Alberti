from rest_framework import serializers
from .models import Muestra, Region, Micrografia

class MuestraSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Muestra
        fields = ["id", "nombre"]
        
class RegionSimpleSerializer(serializers.ModelSerializer):
    muestra = MuestraSimpleSerializer(read_only=True)

    class Meta:
        model = Region
        fields = ["id", "nombre", "muestra"]

class MicrografiaSerializer(serializers.ModelSerializer):
    # region = RegionSimpleSerializer(read_only=True)
    region = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all())    

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


