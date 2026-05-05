from rest_framework.routers import DefaultRouter

from .views import FavoriteViewSet, InvestmentTagViewSet, LeadViewSet, PropertyViewSet

router = DefaultRouter()
router.register(r"properties", PropertyViewSet, basename="property")
router.register(r"favorites", FavoriteViewSet, basename="favorite")
router.register(r"tags", InvestmentTagViewSet, basename="tag")
router.register(r"leads", LeadViewSet, basename="lead")

urlpatterns = router.urls
