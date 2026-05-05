"""Investment scoring engine.

Pure functions. No Django views, no I/O. Easily unit-testable.

Design:
    - Always produce a numeric score 0-100, an ROI range, a rental-yield estimate,
      a demand/trend/risk classification, and an `is_estimated` flag.
    - Prefer city-level data; fall back to country baseline.
    - When inputs are missing we MUST flag `is_estimated=True` so the UI and AI
      can disclose assumptions to the user (anti-hallucination guarantee).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from apps.geo.models import City, Country, DemandChoices, RiskChoices, TrendChoices

DEMAND_WEIGHT = {"low": 5, "medium": 12, "high": 20}
TREND_WEIGHT = {"declining": 0, "stable": 10, "growth": 20}
RISK_PENALTY = {"low": 0, "medium": 8, "high": 18}


@dataclass(frozen=True)
class ScoreResult:
    estimated_roi_min: Decimal
    estimated_roi_max: Decimal
    rental_yield: Decimal
    demand: str
    market_trend: str
    risk_level: str
    investment_score: int
    is_estimated: bool
    notes: str


def _q(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _city_or_country(
    city: Optional[City], country: Country
) -> tuple[Decimal, Decimal, Decimal, str, str, str, bool]:
    """Resolve baseline numbers and the `is_estimated` flag."""

    if city and city.avg_rental_yield is not None and city.investment_score is not None:
        roi_mid = Decimal(city.avg_rental_yield)
        roi_min = max(roi_mid - Decimal("1.5"), Decimal("0"))
        roi_max = roi_mid + Decimal("2.0")
        return (
            roi_min,
            roi_max,
            Decimal(city.avg_rental_yield),
            city.demand or country.base_demand,
            city.trend or country.base_trend,
            city.risk or country.base_risk,
            False,
        )

    return (
        Decimal(country.base_roi_min),
        Decimal(country.base_roi_max),
        Decimal(country.base_rental_yield),
        country.base_demand,
        country.base_trend,
        country.base_risk,
        True,
    )


def compute_score(
    *,
    city: Optional[City],
    country: Country,
    price: Decimal,
    area_sqm: Optional[Decimal],
    is_featured: bool = False,
) -> ScoreResult:
    """Compute a 0-100 investment score.

    Components:
      * 40 pts — yield band (based on rental yield)
      * 20 pts — market demand
      * 20 pts — trend
      * −18 pts — risk penalty
      * +10 pts — value-for-money (price vs city avg/sqm)
      * +5 pts — featured / verified bonus
    """

    roi_min, roi_max, yield_, demand, trend, risk, estimated = _city_or_country(city, country)

    yield_pts = min(40, int(round(float(yield_) * 5)))
    demand_pts = DEMAND_WEIGHT.get(demand, 10)
    trend_pts = TREND_WEIGHT.get(trend, 10)
    risk_pen = RISK_PENALTY.get(risk, 8)

    value_pts = 0
    notes_parts: list[str] = []
    if city and city.avg_price_sqm and area_sqm and area_sqm > 0:
        implied = price / Decimal(area_sqm)
        ratio = float(implied / Decimal(city.avg_price_sqm))
        if ratio < 0.85:
            value_pts = 10
            notes_parts.append(f"Priced ~{int((1 - ratio) * 100)}% below city avg/m².")
        elif ratio < 1.0:
            value_pts = 5
        elif ratio > 1.25:
            value_pts = -8
            notes_parts.append(f"Priced ~{int((ratio - 1) * 100)}% above city avg/m².")

    bonus = 5 if is_featured else 0

    raw = yield_pts + demand_pts + trend_pts + value_pts + bonus - risk_pen
    score = max(0, min(100, raw))

    if estimated:
        notes_parts.append(
            "Score uses country-level baselines; refine with verified city data when available."
        )

    return ScoreResult(
        estimated_roi_min=_q(roi_min),
        estimated_roi_max=_q(roi_max),
        rental_yield=_q(yield_),
        demand=demand,
        market_trend=trend,
        risk_level=risk,
        investment_score=score,
        is_estimated=estimated,
        notes=" ".join(notes_parts),
    )


def upsert_metric(property_obj) -> None:
    """Compute & persist `InvestmentMetric` for a Property."""
    from apps.properties.models import InvestmentMetric

    result = compute_score(
        city=property_obj.city,
        country=property_obj.country,
        price=property_obj.price,
        area_sqm=property_obj.area_sqm,
        is_featured=property_obj.is_featured,
    )
    InvestmentMetric.objects.update_or_create(
        property=property_obj,
        defaults={
            "estimated_roi_min": result.estimated_roi_min,
            "estimated_roi_max": result.estimated_roi_max,
            "rental_yield": result.rental_yield,
            "demand": result.demand,
            "market_trend": result.market_trend,
            "risk_level": result.risk_level,
            "investment_score": result.investment_score,
            "is_estimated": result.is_estimated,
            "notes": result.notes,
        },
    )


# Re-export choice strings for callers that don't want to import geo
__all__ = [
    "ScoreResult",
    "compute_score",
    "upsert_metric",
    "DemandChoices",
    "TrendChoices",
    "RiskChoices",
]
