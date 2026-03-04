from rest_framework.routers import DefaultRouter
from .views import MuestraViewSet, RegionViewSet, MicrografiaViewSet

router = DefaultRouter()
router.register(r'muestras', MuestraViewSet)
router.register(r'regiones', RegionViewSet)
router.register(r'micrografias', MicrografiaViewSet)

urlpatterns = router.urls