from __future__ import annotations

from rest_framework import serializers

from .models import (
    Favorite,
    InvestmentMetric,
    InvestmentTag,
    Lead,
    Property,
    PropertyImage,
)


class InvestmentTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentTag
        fields = ("id", "name", "slug", "color")


class PropertyImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyImage
        fields = ("id", "url", "caption", "position")


class InvestmentMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentMetric
        fields = (
            "estimated_roi_min",
            "estimated_roi_max",
            "rental_yield",
            "demand",
            "market_trend",
            "risk_level",
            "investment_score",
            "is_estimated",
            "notes",
            "computed_at",
        )


class PropertyListSerializer(serializers.ModelSerializer):
    """Compact payload used for grid / search / map cards."""

    country_code = serializers.CharField(source="country.code", read_only=True)
    country_name = serializers.CharField(source="country.name", read_only=True)
    city_name = serializers.CharField(source="city.name", read_only=True)
    primary_image = serializers.CharField(source="primary_image_url", read_only=True)
    metric = InvestmentMetricSerializer(read_only=True)
    tags = InvestmentTagSerializer(many=True, read_only=True)

    class Meta:
        model = Property
        fields = (
            "id",
            "slug",
            "title",
            "property_type",
            "status",
            "price",
            "currency",
            "country_code",
            "country_name",
            "city_name",
            "bedrooms",
            "bathrooms",
            "area_sqm",
            "is_featured",
            "is_premium",
            "primary_image",
            "metric",
            "tags",
            "created_at",
        )


class PropertyDetailSerializer(serializers.ModelSerializer):
    country_code = serializers.CharField(source="country.code", read_only=True)
    country_name = serializers.CharField(source="country.name", read_only=True)
    city_name = serializers.CharField(source="city.name", read_only=True)
    images = PropertyImageSerializer(many=True, read_only=True)
    metric = InvestmentMetricSerializer(read_only=True)
    tags = InvestmentTagSerializer(many=True, read_only=True)

    class Meta:
        model = Property
        fields = (
            "id",
            "slug",
            "owner",
            "title",
            "description",
            "property_type",
            "status",
            "price",
            "currency",
            "country_code",
            "country_name",
            "city_name",
            "address",
            "latitude",
            "longitude",
            "bedrooms",
            "bathrooms",
            "area_sqm",
            "year_built",
            "contact_name",
            "contact_email",
            "contact_phone",
            "is_featured",
            "is_premium",
            "views_count",
            "leads_count",
            "images",
            "metric",
            "tags",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "owner",
            "views_count",
            "leads_count",
            "is_featured",
            "is_premium",
            "created_at",
            "updated_at",
        )


class PropertyWriteSerializer(serializers.ModelSerializer):
    """Used by owners/agencies to create or edit listings."""

    image_urls = serializers.ListField(
        child=serializers.URLField(),
        required=False,
        write_only=True,
        help_text="Optional list of image URLs to attach.",
    )
    tag_slugs = serializers.ListField(
        child=serializers.SlugField(), required=False, write_only=True
    )

    class Meta:
        model = Property
        fields = (
            "title",
            "description",
            "property_type",
            "status",
            "price",
            "currency",
            "country",
            "city",
            "address",
            "latitude",
            "longitude",
            "bedrooms",
            "bathrooms",
            "area_sqm",
            "year_built",
            "contact_name",
            "contact_email",
            "contact_phone",
            "image_urls",
            "tag_slugs",
        )

    def _attach_images(self, prop: Property, urls: list[str]) -> None:
        for i, url in enumerate(urls):
            PropertyImage.objects.create(property=prop, url=url, position=i)

    def _attach_tags(self, prop: Property, slugs: list[str]) -> None:
        if not slugs:
            return
        tags = list(InvestmentTag.objects.filter(slug__in=slugs))
        prop.tags.set(tags)

    def create(self, validated_data: dict) -> Property:
        urls = validated_data.pop("image_urls", [])
        slugs = validated_data.pop("tag_slugs", [])
        prop = Property.objects.create(**validated_data)
        self._attach_images(prop, urls)
        self._attach_tags(prop, slugs)
        return prop

    def update(self, instance: Property, validated_data: dict) -> Property:
        urls = validated_data.pop("image_urls", None)
        slugs = validated_data.pop("tag_slugs", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        if urls is not None:
            instance.images.all().delete()
            self._attach_images(instance, urls)
        if slugs is not None:
            self._attach_tags(instance, slugs)
        return instance


class FavoriteSerializer(serializers.ModelSerializer):
    property = PropertyListSerializer(read_only=True)
    property_id = serializers.PrimaryKeyRelatedField(
        queryset=Property.objects.all(), source="property", write_only=True
    )

    class Meta:
        model = Favorite
        fields = ("id", "property", "property_id", "created_at")
        read_only_fields = ("id", "created_at")


class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = ("id", "property", "name", "email", "phone", "message", "created_at")
        read_only_fields = ("id", "created_at")
