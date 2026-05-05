from django.contrib import admin

from .models import City, Country


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "currency", "base_roi_min", "base_roi_max", "base_trend", "base_risk")
    search_fields = ("code", "name")


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "avg_price_sqm", "avg_rental_yield", "investment_score", "trend", "risk")
    list_filter = ("country", "trend", "risk", "demand")
    search_fields = ("name", "country__name")
    prepopulated_fields = {"slug": ("name",)}
