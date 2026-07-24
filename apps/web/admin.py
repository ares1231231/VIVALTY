from datetime import datetime, time, timedelta

from django.contrib import admin
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.template.response import TemplateResponse
from django.utils import timezone

from apps.billing.models import FeaturedListingPurchase, Subscription
from apps.properties.models import Lead, Property, Status
from apps.users.models import User

from .models import (
    DailyPageView,
    DailyVisitor,
    InvestorInquiry,
    SavedSearch,
    SiteStats,
    Testimonial,
)

TREND_DAYS = 14
TOP_PAGES_DAYS = 7
TOP_PAGES_LIMIT = 15


def _daily_counts(qs, date_field: str, since) -> dict:
    """Map date -> row count for a queryset, from ``since`` (a date) onwards."""
    since_dt = timezone.make_aware(datetime.combine(since, time.min))
    rows = (
        qs.filter(**{f"{date_field}__gte": since_dt})
        .annotate(day=TruncDate(date_field))
        .values("day")
        .annotate(n=Count("pk"))
    )
    return {r["day"]: r["n"] for r in rows}


def _with_bar_pct(entries: list[dict], key: str) -> None:
    """Precompute bar widths (0–100) so the template stays logic-free."""
    peak = max((e[key] for e in entries), default=0) or 1
    for e in entries:
        e[f"{key}_pct"] = round(e[key] * 100 / peak)


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


@admin.register(SiteStats)
class SiteStatsAdmin(admin.ModelAdmin):
    """Read-only dashboard: signups, real visits, top pages and business KPIs."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        now = timezone.now()
        today = timezone.localdate()
        trend_start = today - timedelta(days=TREND_DAYS - 1)
        week_ago = today - timedelta(days=6)

        # ---- daily trend series (last TREND_DAYS days) -------------------
        signups = _daily_counts(User.objects.all(), "date_joined", trend_start)
        leads = _daily_counts(Lead.objects.all(), "created_at", trend_start)
        views = {
            r["date"]: r["n"]
            for r in DailyPageView.objects.filter(date__gte=trend_start)
            .values("date")
            .annotate(n=Sum("count"))
        }
        visitors = {
            r["date"]: r["n"]
            for r in DailyVisitor.objects.filter(date__gte=trend_start)
            .values("date")
            .annotate(n=Count("pk"))
        }
        days = []
        for offset in range(TREND_DAYS - 1, -1, -1):
            day = today - timedelta(days=offset)
            days.append(
                {
                    "date": day,
                    "signups": signups.get(day, 0),
                    "views": views.get(day, 0),
                    "visitors": visitors.get(day, 0),
                    "leads": leads.get(day, 0),
                }
            )
        for key in ("signups", "views", "visitors", "leads"):
            _with_bar_pct(days, key)

        # ---- top pages (last TOP_PAGES_DAYS days) ------------------------
        top_pages = list(
            DailyPageView.objects.filter(date__gte=today - timedelta(days=TOP_PAGES_DAYS - 1))
            .values("path")
            .annotate(total=Sum("count"))
            .order_by("-total")[:TOP_PAGES_LIMIT]
        )
        _with_bar_pct(top_pages, "total")

        # ---- headline KPIs -----------------------------------------------
        def _sum_days(key: str, since) -> int:
            return sum(d[key] for d in days if d["date"] >= since)

        kpis = {
            "users_total": User.objects.count(),
            "users_today": days[-1]["signups"],
            "users_7d": _sum_days("signups", week_ago),
            "visitors_today": days[-1]["visitors"],
            "visitors_7d": _sum_days("visitors", week_ago),
            "views_today": days[-1]["views"],
            "views_7d": _sum_days("views", week_ago),
            "leads_total": Lead.objects.count(),
            "leads_7d": _sum_days("leads", week_ago),
            "listings_active": Property.objects.filter(status=Status.ACTIVE).count(),
            "listings_pending": Property.objects.filter(status=Status.PENDING).count(),
            "newsletter_emails": InvestorInquiry.objects.filter(
                source_page__startswith="newsletter_"
            ).count(),
            "subs_active": Subscription.objects.filter(
                status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING]
            ).count(),
            "boosts_active": FeaturedListingPurchase.objects.filter(ends_at__gt=now).count(),
            "boost_revenue": FeaturedListingPurchase.objects.aggregate(t=Sum("amount"))["t"] or 0,
        }

        recent_users = User.objects.order_by("-date_joined")[:10]

        context = {
            **self.admin_site.each_context(request),
            "title": "Site statistics",
            "kpis": kpis,
            "days": days,
            "top_pages": top_pages,
            "recent_users": recent_users,
            "trend_days": TREND_DAYS,
            "top_pages_days": TOP_PAGES_DAYS,
            "opts": self.model._meta,
        }
        return TemplateResponse(request, "admin/web/site_stats.html", context)
