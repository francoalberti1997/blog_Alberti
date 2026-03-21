from django.contrib import admin

from .models import Micrografia, Region, Muestra, Material, Categoria, Micrografia_mask, GrainSize, MicrographyMeasure

# Register your models here.
admin.site.register(Muestra)
admin.site.register(Region) 
admin.site.register(Micrografia)
admin.site.register(Material)
admin.site.register(Categoria)
admin.site.register(Micrografia_mask)
admin.site.register(GrainSize)
admin.site.register(MicrographyMeasure)