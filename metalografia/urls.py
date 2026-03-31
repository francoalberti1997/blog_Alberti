from rest_framework.routers import DefaultRouter, path
from .views import *

router = DefaultRouter()
router.register(r'muestras', MuestraViewSet, basename='muestra')
router.register(r'regiones', RegionViewSet, basename='region')
router.register(r'micrografias', MicrografiaViewSet, basename='micrografia')

urlpatterns = router.urls

urlpatterns += [
    path("predict/<int:micrografia_id>/", PredictView.as_view(), name="predict"),
    path("mask/<int:micrografia_id>/", GetMask.as_view()),
    path("grain_size/<int:region_id>/", GrainMeasureView.as_view(), name="grain_size"),#Aplica algoritmo de medición en 1 sola micrografía
    # path("micrografia_measure/<int:micrografia_id>/", MicrografiaMeasureView.as_view(), name="micrografia_measure"),#Get de la medición de la micrografía
#     path("region_measure/<int:region_id>/", RegionMeasureView.as_view(), name="region_size"), #Get de la medición de la región (promedio de las micrografías)
    # path("build_report/<int:muestra_id>/", BuildReport.as_view(), name="build_report"),#Armar reporte.
    # path("mask_phases/<int:micrografia_id>/", MaskPhasesView.as_view(), name="mask_phases"),#Generar máscara de fases
]