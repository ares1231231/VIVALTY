from django.contrib import admin

from .models import InvestorInquiry, SavedSearch, Testimonial


@admin.register(SavedSearch)
class SavedSearchAdmin(admin.ModelAdmin):
    list_display = ("label", "user", "frequency", "is_active", "last_sent_at", "created_at")
    list_filter = ("frequency", "is_active", "created_at")
    search_fields = ("label", "query", "user__email")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "rating", "is_active", "order", "created_at")
    list_filter = ("is_active", "rating")
    search_fields = ("name", "location", "quote")
    list_editable = ("is_active", "order")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"


@admin.register(InvestorInquiry)
class InvestorInquiryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "profile",
        "budget_max",
        "budget_currency",
        "markets_of_interest",
        "source_page",
        "created_at",
    )
    list_filter = ("profile", "source_page", "created_at")
    search_fields = ("name", "email", "markets_of_interest", "message")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
