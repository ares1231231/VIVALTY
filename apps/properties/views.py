from __future__ import annotations

from django.db.models import F
from rest_framework import filters, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .filters import PropertyFilter
from .models import Favorite, InvestmentTag, Lead, Property
from .permissions import IsOwnerOrReadOnly
from .serializers import (
    FavoriteSerializer,
    InvestmentTagSerializer,
    LeadSerializer,
    PropertyDetailSerializer,
    PropertyListSerializer,
    PropertyWriteSerializer,
)


class PropertyViewSet(viewsets.ModelViewSet):
    """CRUD for properties + actions: favorite, lead, similar."""

    queryset = (
        Property.objects.select_related("country", "city", "metric")
        .prefetch_related("images", "tags")
        .all()
    )
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly)
    filterset_class = PropertyFilter
    # Use project-level DEFAULT_FILTER_BACKENDS; just declare the fields:
    search_fields = ("title", "description", "city__name", "country__name", "address")
    ordering_fields = (
        "price",
        "created_at",
        "metric__investment_score",
        "metric__estimated_roi_max",
    )
    ordering = ("-is_featured", "-created_at")

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action in {"list", "retrieve"}:
            qs = qs.exclude(status__in=["draft", "archived"])
        # Owners always see their own listings, including drafts, on /mine
        return qs

    def get_serializer_class(self):
        if self.action in {"list"}:
            return PropertyListSerializer
        if self.action in {"create", "update", "partial_update"}:
            return PropertyWriteSerializer
        return PropertyDetailSerializer

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError

        from apps.billing.services.quotas import can_create_listing

        allowed, quota_msg = can_create_listing(self.request.user)
        if not allowed:
            raise ValidationError({"detail": quota_msg})
        serializer.save(owner=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        Property.objects.filter(pk=instance.pk).update(views_count=F("views_count") + 1)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    # ----- Custom actions ---------------------------------------------------

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def mine(self, request):
        qs = self.get_queryset().filter(owner=request.user)
        page = self.paginate_queryset(qs)
        ser = PropertyListSerializer(page or qs, many=True)
        return self.get_paginated_response(ser.data) if page is not None else Response(ser.data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def favorite(self, request, pk=None):
        prop = self.get_object()
        fav, created = Favorite.objects.get_or_create(user=request.user, property=prop)
        if not created:
            fav.delete()
            return Response({"favorited": False})
        return Response({"favorited": True}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[permissions.AllowAny])
    def lead(self, request, pk=None):
        prop = self.get_object()
        ser = LeadSerializer(data={**request.data, "property": prop.pk})
        ser.is_valid(raise_exception=True)
        ser.save(
            user=request.user if request.user.is_authenticated else None,
            property=prop,
        )
        Property.objects.filter(pk=prop.pk).update(leads_count=F("leads_count") + 1)
        return Response(ser.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def similar(self, request, pk=None):
        prop = self.get_object()
        qs = (
            self.get_queryset()
            .filter(country=prop.country, property_type=prop.property_type)
            .exclude(pk=prop.pk)
            .order_by("-metric__investment_score")[:8]
        )
        return Response(PropertyListSerializer(qs, many=True).data)


class FavoriteViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = FavoriteSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return (
            Favorite.objects.select_related("property__country", "property__city", "property__metric")
            .filter(user=self.request.user)
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class InvestmentTagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InvestmentTag.objects.all()
    serializer_class = InvestmentTagSerializer
    permission_classes = (permissions.AllowAny,)


class LeadViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Owners read leads on their own listings."""

    serializer_class = LeadSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return (
            Lead.objects.select_related("property")
            .filter(property__owner=self.request.user)
            .order_by("-created_at")
        )
