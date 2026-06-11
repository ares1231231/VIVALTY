"""Investment scoring engine — explainable, deterministic, RAG-friendly.

Pure functions. No Django views, no I/O. Easily unit-testable.

Design contract:
    - Always produce a numeric score 0-100, an ROI range, a rental-yield estimate,
      a demand/trend/risk classification, an `is_estimated` flag and a structured
      `breakdown` payload that the UI / AI advisor can render verbatim.
    - Prefer city-level data; fall back to country baseline.
    - When inputs are missing we MUST flag `is_estimated=True` so the UI and AI
      can disclose assumptions to the user (anti-hallucination guarantee).

The breakdown payload is the source of truth for the "How Our AI Score Works"
methodology page. Never invent strengths/risks in the templates — read them
from `metric.score_breakdown` and let admins/owners refresh the score by
re-running `upsert_metric`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from apps.geo.models import City, Country, DemandChoices, RiskChoices, TrendChoices

# ──────────────────────────────────────────────────────────────────────────────
# Public weight table — surfaced verbatim on the methodology page.
# A change here MUST be reflected on /methodology/ via the same constants.
# ──────────────────────────────────────────────────────────────────────────────
FACTOR_WEIGHTS = {
    "yield": 40,           # rental yield (0-40 pts)
    "demand": 20,          # local rental demand (0-20 pts)
    "trend": 20,           # 12-month price trend (0-20 pts)
    "value_for_money": 10, # price vs city avg/m² (-8 to +10 pts)
    "verification": 5,     # featured / agency-verified bonus (0-5 pts)
    "risk_penalty": 18,    # subtracted: country/city risk (0 to -18 pts)
}

DEMAND_WEIGHT = {"low": 5, "medium": 12, "high": 20}
TREND_WEIGHT = {"declining": 0, "stable": 10, "growth": 20}
RISK_PENALTY = {"low": 0, "medium": 8, "high": 18}

DEMAND_LABEL = {"low": "Low rental demand", "medium": "Steady rental demand", "high": "Strong rental demand"}
TREND_LABEL = {"declining": "Cooling market", "stable": "Stable market", "growth": "Appreciating market"}
RISK_LABEL = {"low": "Low country risk", "medium": "Medium country risk", "high": "Elevated country risk"}


@dataclass(frozen=True)
class FactorScore:
    """A single factor that fed the final score."""

    key: str
    label: str
    points: int
    max_points: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "points": self.points,
            "max_points": self.max_points,
            "detail": self.detail,
            "pct": int(round((self.points / self.max_points) * 100)) if self.max_points else 0,
        }


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
    breakdown: dict[str, Any] = field(default_factory=dict)


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
    """Compute a 0-100 investment score with a fully explainable breakdown.

    The returned ``breakdown`` payload is shaped to be persisted as JSON and
    rendered directly in templates — UI code never recomputes anything.
    """

    roi_min, roi_max, yield_, demand, trend, risk, estimated = _city_or_country(city, country)

    # ── Factor: yield ────────────────────────────────────────────────────────
    yield_pts = min(40, int(round(float(yield_) * 5)))
    yield_factor = FactorScore(
        key="yield",
        label="Rental yield",
        points=yield_pts,
        max_points=FACTOR_WEIGHTS["yield"],
        detail=f"Gross rental yield estimated at {float(yield_):.1f}% per year.",
    )

    # ── Factor: demand ───────────────────────────────────────────────────────
    demand_pts = DEMAND_WEIGHT.get(demand, 10)
    demand_factor = FactorScore(
        key="demand",
        label="Rental demand",
        points=demand_pts,
        max_points=FACTOR_WEIGHTS["demand"],
        detail=DEMAND_LABEL.get(demand, "Demand profile unavailable."),
    )

    # ── Factor: market trend ─────────────────────────────────────────────────
    trend_pts = TREND_WEIGHT.get(trend, 10)
    trend_factor = FactorScore(
        key="trend",
        label="Market trend",
        points=trend_pts,
        max_points=FACTOR_WEIGHTS["trend"],
        detail=TREND_LABEL.get(trend, "Trend signal unavailable."),
    )

    # ── Factor: value-for-money (vs city avg €/m²) ──────────────────────────
    value_pts = 0
    value_detail = "Insufficient area or city benchmark to assess price/m²."
    if city and city.avg_price_sqm and area_sqm and area_sqm > 0:
        implied = price / Decimal(area_sqm)
        ratio = float(implied / Decimal(city.avg_price_sqm))
        if ratio < 0.85:
            value_pts = 10
            value_detail = f"Asking price is ~{int((1 - ratio) * 100)}% below {city.name}'s €/m² benchmark."
        elif ratio < 1.0:
            value_pts = 5
            value_detail = f"Asking price is slightly below {city.name}'s €/m² benchmark."
        elif ratio <= 1.25:
            value_pts = 0
            value_detail = f"Asking price is in line with {city.name}'s €/m² benchmark."
        else:
            value_pts = -8
            value_detail = f"Asking price is ~{int((ratio - 1) * 100)}% above {city.name}'s €/m² benchmark."
    value_factor = FactorScore(
        key="value_for_money",
        label="Value for money",
        points=value_pts,
        max_points=FACTOR_WEIGHTS["value_for_money"],
        detail=value_detail,
    )

    # ── Factor: verification ─────────────────────────────────────────────────
    verification_pts = 5 if is_featured else 0
    verification_factor = FactorScore(
        key="verification",
        label="Verification",
        points=verification_pts,
        max_points=FACTOR_WEIGHTS["verification"],
        detail="Listing reviewed by Vivalty's editorial desk." if is_featured
        else "Standard listing — no editorial verification yet.",
    )

    # ── Factor: risk penalty (subtracted) ────────────────────────────────────
    risk_pen = RISK_PENALTY.get(risk, 8)
    risk_factor = FactorScore(
        key="risk_penalty",
        label="Country / city risk",
        points=-risk_pen,
        max_points=FACTOR_WEIGHTS["risk_penalty"],
        detail=RISK_LABEL.get(risk, "Risk profile unavailable."),
    )

    raw = (
        yield_pts + demand_pts + trend_pts + value_pts + verification_pts - risk_pen
    )
    score = max(0, min(100, raw))

    # ── Strengths & risks (human-readable, derived from factor signals) ─────
    strengths: list[str] = []
    risks: list[str] = []

    if yield_pts >= 30:
        strengths.append(f"High projected yield ({float(yield_):.1f}%) for the asset class.")
    elif yield_pts <= 15:
        risks.append("Yield is below benchmark for international real estate income strategies.")

    if demand == "high":
        strengths.append("Strong rental demand in the local market reduces vacancy risk.")
    elif demand == "low":
        risks.append("Soft local demand may extend rent-up periods.")

    if trend == "growth":
        strengths.append("Capital values are trending up in this market.")
    elif trend == "declining":
        risks.append("Local price trend is softening — capital appreciation is not guaranteed.")

    if value_pts >= 5:
        strengths.append(value_detail)
    elif value_pts < 0:
        risks.append(value_detail)

    if risk == "high":
        risks.append("Country risk profile is elevated — currency and policy considerations apply.")
    elif risk == "low" and risk_pen == 0:
        strengths.append("Mature, low-risk jurisdiction.")

    if estimated:
        risks.append(
            "Some inputs use country-level baselines; refine with verified city data when available."
        )
    if is_featured:
        strengths.append("Editorially verified by Vivalty's editorial desk.")

    notes_parts: list[str] = []
    if value_detail and value_pts != 0:
        notes_parts.append(value_detail)
    if estimated:
        notes_parts.append(
            "Score uses country-level baselines; refine with verified city data when available."
        )

    factors = [
        yield_factor,
        demand_factor,
        trend_factor,
        value_factor,
        verification_factor,
        risk_factor,
    ]

    breakdown: dict[str, Any] = {
        "version": 2,
        "final_score": score,
        "raw_total": raw,
        "factors": [f.to_dict() for f in factors],
        "strengths": strengths,
        "risks": risks,
        "inputs": {
            "yield_pct": float(yield_),
            "roi_min_pct": float(roi_min),
            "roi_max_pct": float(roi_max),
            "demand": demand,
            "trend": trend,
            "risk": risk,
            "is_estimated": estimated,
            "city_avg_price_sqm": float(city.avg_price_sqm) if (city and city.avg_price_sqm) else None,
            "implied_price_sqm": float(price / Decimal(area_sqm)) if (area_sqm and area_sqm > 0) else None,
        },
    }

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
        breakdown=breakdown,
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
            "score_breakdown": result.breakdown,
        },
    )


__all__ = [
    "ScoreResult",
    "FactorScore",
    "FACTOR_WEIGHTS",
    "compute_score",
    "upsert_metric",
    "DemandChoices",
    "TrendChoices",
    "RiskChoices",
]
