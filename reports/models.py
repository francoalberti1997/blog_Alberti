from django.db import models
from member.models import Member
import random
import string

def generate_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

class ReportPDF(models.Model):
    
    file = models.FileField(
        upload_to="reports/",   
        blank=True,
        null=True,
        max_length=500                   
    )

    status = models.CharField(max_length=50, default="pending")
    
    fecha = models.DateTimeField(auto_now_add=True)
    
    owner = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, blank=True, related_name="owner_reports")
    
    muestra = models.ForeignKey("metalografia.Muestra", on_delete=models.SET_NULL, null=True, blank=True, related_name="report_muestra")
    
    value = models.CharField(max_length=8, default=generate_code, blank=True, null=True)

    has_mask = models.BooleanField(default=False)

    
