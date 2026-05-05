from rest_framework.routers import DefaultRouter

from .views import AIConversationViewSet

router = DefaultRouter()
router.register(r"sessions", AIConversationViewSet, basename="ai-session")

urlpatterns = router.urls
