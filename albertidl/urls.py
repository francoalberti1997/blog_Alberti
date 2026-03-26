
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from . import views 

urlpatterns = [
    path('admin/', admin.site.urls),
    path('blogs/', include('blogs.urls')),
    path('member/', include('member.urls')),
    path('metalografia/', include('metalografia.urls')),
    path("ping/", views.ping_view, name="ping"),
    path("create-superuser/", views.create_superuser_view, name="create_superuser"),
    path("reports/", include("reports.urls")),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    