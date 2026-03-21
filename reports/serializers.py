from rest_framework import serializers
from .models import ReportPDF

class ReportPDFSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportPDF
        fields = [
            "id",
            "value",
            "status",
            "fecha",
            "file",
            "owner",
            "muestra",
        ]