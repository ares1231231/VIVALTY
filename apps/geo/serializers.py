from __future__ import annotations

from rest_framework import serializers

from .models import City, Country


class CitySerializer(serializers.ModelSerializer):
    country_code = serializers.CharField(source="country.code", read_only=True)
    country_name = serializers.CharField(source="country.name", read_only=True)

    class Meta:
        model = City
        fields = (
            "id",
            "name",
            "slug",
            "country_code",
            "country_name",
            "population",
            "avg_price_sqm",
            "avg_rental_yield",
            "demand",
            "trend",
            "risk",
            "investment_score",
            "summary",
        )


class CountrySerializer(serializers.ModelSerializer):
    cities_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Country
        fields = (
            "id",
            "code",
            "name",
            "currency",
            "flag_emoji",
            "base_roi_min",
            "base_roi_max",
            "base_rental_yield",
            "base_demand",
            "base_trend",
            "base_risk",
            "summary",
            "cities_count",
        )
