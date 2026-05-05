from __future__ import annotations

from django.db.models import Count
from rest_framework import filters, viewsets

from .models import City, Country
from .serializers import CitySerializer, CountrySerializer


class CountryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Country.objects.annotate(cities_count=Count("cities")).all()
    serializer_class = CountrySerializer
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("name", "code")
    ordering_fields = ("name", "code")
    lookup_field = "code"


class CityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = City.objects.select_related("country").all()
    serializer_class = CitySerializer
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("name", "country__name", "country__code")
    ordering_fields = ("name", "investment_score", "avg_price_sqm")

    def get_queryset(self):
        qs = super().get_queryset()
        country = self.request.query_params.get("country")
        if country:
            qs = qs.filter(country__code__iexact=country)
        return qs
