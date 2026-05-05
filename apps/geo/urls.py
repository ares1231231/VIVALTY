from rest_framework.routers import DefaultRouter

from .views import CityViewSet, CountryViewSet

router = DefaultRouter()
router.register(r"countries", CountryViewSet, basename="country")
router.register(r"cities", CityViewSet, basename="city")

urlpatterns = router.urls
