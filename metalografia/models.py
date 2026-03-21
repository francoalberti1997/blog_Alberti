from django.db import models
import numpy as np
from member.models import Member, Company

class Categoria(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre
    
class Material(models.Model):
    nombre = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    has_model = models.BooleanField(default=False)

    def __str__(self):
        return self.nombre

class Muestra(models.Model):
    nombre = models.CharField(max_length=100)
    owner = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name="owner_muestras")
    material = models.ForeignKey(Material, on_delete=models.SET_NULL, null=True, related_name="muestras")
    informacion = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)
    imagen = models.ImageField(upload_to="media/muestras/")
    categoria = models.ForeignKey("Categoria", on_delete=models.SET_NULL, null=True, blank=True, related_name="muestras")

    def __str__(self):
        return self.nombre + f" self.id: {self.id}"


class Region(models.Model):
    muestra = models.ForeignKey(Muestra, on_delete=models.CASCADE, related_name="muestra")
    nombre = models.CharField(max_length=100)
    imagen = models.ImageField(upload_to="media/regiones/", blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} ({self.muestra.nombre}), id: {self.id}"

    def get_or_create_size(self):
        grain_size, created = GrainSize.objects.get_or_create(region=self)
        return grain_size

class Micrografia(models.Model):
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name="micrografias")
    nombre = models.CharField(max_length=100)
    imagen = models.ImageField(upload_to="media/micrografias/")
    um_by_px = models.FloatField(null=True, blank=True) #pixeles por micrómetro

    def __str__(self):
        return f"{self.nombre} id: {self.id}"

class Micrografia_mask(models.Model):
    micrografia = models.OneToOneField(Micrografia, on_delete=models.CASCADE, related_name="micrografias_mask")
    nombre = models.CharField(max_length=100)
    imagen = models.ImageField(upload_to="media/micrografias_mask/", blank=True, null=True)
    status = models.CharField(max_length=50, default="pending")

    def __str__(self):
        return f"{self.nombre} ({self.micrografia.nombre}), id: {self.id}"

    def verify_model(self):
        return self.micrografia.region.muestra.material.has_model

class GrainSize(models.Model):
    """
    mean_size y standard_deviation están en unidades métricas.
    """
    mean_size = models.FloatField(blank=True, null=True)
    region = models.OneToOneField(Region, on_delete=models.CASCADE, related_name="region_measure")
    standard_deviation = models.FloatField(null=True, blank=True)

    def compute_from_micrograph_measures(self):
        values_um = []

        for micro in self.region.micrografias.all():
            try:
                measure = micro.measure_micro
            except MicrographyMeasure.DoesNotExist:
                continue

            if measure.mean_size is None:
                continue

            if micro.um_by_px is None:
                continue

            mean_um, _ = measure.convert_from_px_to_um()
            values_um.append(mean_um)

            print(f"Falló para: {micro} en region: {self.region.nombre}")


        if not values_um and self.region.micrografias.exists():
            print(values_um)
            raise ValueError("No hay mediciones válidas para calcular GrainSize")

        self.mean_size = float(np.mean(values_um))
        self.standard_deviation = float(np.std(values_um))
        self.save()

        return self.mean_size, self.standard_deviation

class MicrographyMeasure(models.Model):
    """
    mean_size y standard_deviation están en píxeles.
    """
    mean_size = models.FloatField(blank=True, null=True)
    standard_deviation = models.FloatField(null=True, blank=True)   
    micrografia = models.OneToOneField(Micrografia, on_delete=models.CASCADE, related_name="measure_micro")

    def convert_from_px_to_um(self):
        if self.micrografia.um_by_px is None:
            raise ValueError(f"La micrografía {self.micrografia} no tiene definido um_by_px")
        return self.mean_size * self.micrografia.um_by_px, self.standard_deviation * self.micrografia.um_by_px
    
    
