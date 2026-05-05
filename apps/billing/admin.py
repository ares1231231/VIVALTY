from django.contrib import admin

from .models import FeaturedListingPurchase, Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "monthly_price", "yearly_price", "currency", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "current_period_end", "created_at")
    list_filter = ("status", "plan")
    search_fields = ("user__email", "external_ref")


@admin.register(FeaturedListingPurchase)
class FeaturedListingPurchaseAdmin(admin.ModelAdmin):
    list_display = ("property", "user", "amount", "currency", "starts_at", "ends_at")
    list_filter = ("currency",)
    search_fields = ("property__title", "user__email")
