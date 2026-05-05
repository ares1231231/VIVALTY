from django.contrib import admin

from .models import (
    Favorite,
    InvestmentMetric,
    InvestmentTag,
    Lead,
    Property,
    PropertyImage,
)


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1


class InvestmentMetricInline(admin.StackedInline):
    model = InvestmentMetric
    extra = 0
    can_delete = False
    readonly_fields = ("computed_at",)


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        "title", "country", "city", "property_type", "status",
        "price", "currency", "is_featured", "is_premium", "created_at",
    )
    list_filter = ("status", "country", "property_type", "is_featured", "is_premium")
    search_fields = ("title", "description", "address", "city__name", "country__name")
    autocomplete_fields = ("country", "city", "owner")
    inlines = (PropertyImageInline, InvestmentMetricInline)
    actions = ("mark_featured", "unmark_featured")

    @admin.action(description="Mark selected as Featured")
    def mark_featured(self, request, queryset):
        queryset.update(is_featured=True)

    @admin.action(description="Unmark Featured")
    def unmark_featured(self, request, queryset):
        queryset.update(is_featured=False)


@admin.register(InvestmentTag)
class InvestmentTagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "color")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


admin.site.register(Favorite)
admin.site.register(Lead)
