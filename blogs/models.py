from django.db import models

class Author(models.Model):
    name = models.CharField(max_length=100)
    image = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name

class Blog(models.Model):
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=500, blank=True, null=True)
    body = models.CharField(max_length=10000, blank=True, null=True)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, blank=True, null=True)
    category = models.CharField(max_length=50)
    date = models.DateField()
    read_time = models.CharField(max_length=20)
    image = models.URLField()
    is_featured = models.BooleanField(default=False)
    youtube_id = models.CharField(max_length=20, blank=True, null=True)
    
    def __str__(self):
        return f"{self.title} by {self.author}"
