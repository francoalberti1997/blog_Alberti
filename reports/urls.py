from rest_framework.routers import DefaultRouter, path
from .views import *


urlpatterns = [
    path("pdf/", GeneratePDF.as_view(), name="generate_pdf"),
    path("<int:id>/", TrackPDF.as_view(), name="check_pdf"),

]