from django.db import models

class Categoria(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre

class Muestra(models.Model):
    nombre = models.CharField(max_length=100)
    material = models.CharField(max_length=100)
    informacion = models.TextField()
    fecha = models.DateField()
    imagen = models.ImageField(upload_to="muestras/")
    categoria = models.ForeignKey("Categoria", on_delete=models.SET_NULL, null=True, related_name="muestras")

    def __str__(self):
        return self.nombre


class Region(models.Model):
    muestra = models.ForeignKey(Muestra, on_delete=models.CASCADE, related_name="regiones")
    nombre = models.CharField(max_length=100)
    imagen = models.ImageField(upload_to="regiones/", blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} ({self.muestra.nombre})"


class Micrografia(models.Model):
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name="micrografias")
    nombre = models.CharField(max_length=100)
    imagen = models.ImageField(upload_to="micrografias/")

    def __str__(self):
        return f"{self.nombre} ({self.region.nombre})"

class Micrografia_mask(models.Model):
    micrografia = models.ForeignKey(Micrografia, on_delete=models.CASCADE, related_name="micrografias_mask")
    nombre = models.CharField(max_length=100)
    imagen = models.ImageField(upload_to="micrografias_mask/")

    def __str__(self):
        return f"{self.nombre} ({self.micrografia.nombre})"