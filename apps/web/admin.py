from django.contrib import admin

from .models import InvestorInquiry


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
