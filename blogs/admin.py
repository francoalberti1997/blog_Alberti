from django.contrib import admin
from .models import Blog
from .models import Author


admin.site.register(Blog)

admin.site.register(Author)