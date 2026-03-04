from django.contrib import admin

from modelos.models import Micrografia, Region, Muestra

# Register your models here.
admin.site.register(Muestra)
admin.site.register(Region) 
admin.site.register(Micrografia)