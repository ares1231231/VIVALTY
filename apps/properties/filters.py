from __future__ import annotations

from django_filters import rest_framework as df

from .models import Property, PropertyType, Status


class PropertyFilter(df.FilterSet):
    country = df.CharFilter(field_name="country__code", lookup_expr="iexact")
    city = df.CharFilter(field_name="city__slug", lookup_expr="iexact")
    city_name = df.CharFilter(field_name="city__name", lookup_expr="icontains")
    type = df.MultipleChoiceFilter(field_name="property_type", choices=PropertyType.choices)
    status = df.MultipleChoiceFilter(field_name="status", choices=Status.choices)

    price_min = df.NumberFilter(field_name="price", lookup_expr="gte")
    price_max = df.NumberFilter(field_name="price", lookup_expr="lte")

    bedrooms_min = df.NumberFilter(field_name="bedrooms", lookup_expr="gte")
    area_min = df.NumberFilter(field_name="area_sqm", lookup_expr="gte")

    score_min = df.NumberFilter(field_name="metric__investment_score", lookup_expr="gte")
    roi_min = df.NumberFilter(field_name="metric__estimated_roi_min", lookup_expr="gte")

    tag = df.CharFilter(field_name="tags__slug", lookup_expr="iexact")
    is_featured = df.BooleanFilter(field_name="is_featured")
    is_premium = df.BooleanFilter(field_name="is_premium")

    class Meta:
        model = Property
        fields = ("country", "city", "type", "status", "price_min", "price_max")
