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
        "title", "listing_ref", "listing_agency",
        "country", "city", "property_type", "status",
        "price", "currency", "is_featured", "is_premium", "created_at",
    )
    list_filter = ("status", "country", "property_type", "is_featured", "is_premium")
    search_fields = (
        "title", "description", "address", "listing_ref", "listing_agency",
        "city__name", "country__name",
    )
    autocomplete_fields = ("country", "city", "owner")
    inlines = (PropertyImageInline, InvestmentMetricInline)
    actions = (
        "approve_listings",
        "archive_listings",
        "mark_featured",
        "unmark_featured",
        "mark_premium",
        "rescore",
    )

    @admin.action(description="Approve selected (pending → active)")
    def approve_listings(self, request, queryset):
        """Editorial approval: flip owner-submitted listings from PENDING to ACTIVE
        so they appear in the public marketplace. Refreshes the AI score so the
        published listing carries a current snapshot.
        """
        from apps.properties.services.scoring import upsert_metric

        approved = queryset.filter(status="pending")
        count = approved.count()
        approved.update(status="active")
        for prop in Property.objects.filter(pk__in=approved.values_list("pk", flat=True)):
            upsert_metric(prop)
        self.message_user(request, f"Approved {count} listing(s) — now live.")

    @admin.action(description="Archive selected (hide from marketplace)")
    def archive_listings(self, request, queryset):
        count = queryset.update(status="archived")
        self.message_user(request, f"Archived {count} listing(s).")

    @admin.action(description="Mark selected as Featured")
    def mark_featured(self, request, queryset):
        # featured_until=None → editorial; expire_featured never strips these.
        queryset.update(is_featured=True, featured_until=None)

    @admin.action(description="Unmark Featured")
    def unmark_featured(self, request, queryset):
        queryset.update(is_featured=False, featured_until=None)

    @admin.action(description="Mark selected as Premium")
    def mark_premium(self, request, queryset):
        queryset.update(is_premium=True)

    @admin.action(description="Recompute investment score")
    def rescore(self, request, queryset):
        from apps.properties.services.scoring import upsert_metric

        for prop in queryset:
            upsert_metric(prop)


@admin.register(InvestmentMetric)
class InvestmentMetricAdmin(admin.ModelAdmin):
    list_display = (
        "property",
        "investment_score",
        "rental_yield",
        "estimated_roi_min",
        "estimated_roi_max",
        "demand",
        "market_trend",
        "risk_level",
        "is_estimated",
        "computed_at",
    )
    list_filter = ("demand", "market_trend", "risk_level", "is_estimated")
    search_fields = ("property__title",)
    readonly_fields = ("computed_at", "score_breakdown")


@admin.register(InvestmentTag)
class InvestmentTagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "color")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


admin.site.register(Favorite)


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "property", "status", "created_at")
    list_filter = ("status", "created_at", "property__country")
    search_fields = ("name", "email", "phone", "message", "property__title")
    list_editable = ("status",)
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
