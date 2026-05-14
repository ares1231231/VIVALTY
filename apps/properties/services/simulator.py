"""Investment cashflow simulator.

Pure functions, deterministic, no I/O. Used by:
    - the Investment Simulator page (full-screen Bloomberg-style modeller),
    - the property-detail "Run a scenario" widget,
    - the side-by-side comparison page (one row of metrics per property).

We deliberately keep all assumptions explicit and country-aware. Every figure
returned to the UI carries a label so that the disclosure / confidence layer
on the methodology page can mirror the maths exactly.

Tax/fee schedules below are reasonable mid-2026 rules-of-thumb — they are
exposed as overridable inputs so analysts and the finance team can refine the
model without touching templates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Country-level assumptions. Calibrated to be conservative; each value is
# documented (and surfaced verbatim on /methodology/) so investors know the
# exact maths behind every output number.
# ─────────────────────────────────────────────────────────────────────────────
COUNTRY_ASSUMPTIONS: dict[str, dict[str, float]] = {
    # Acquisition fees % of price (notary, transfer tax, agent on buy-side).
    # Annual operating fees % of gross rent (mgmt + maintenance + vacancy buffer).
    # Income-tax rate applied on net rent.
    # Long-run capital-appreciation %/yr (used in 5y/10y projection).
    "FR": {"acquisition_fees": 7.5,  "operating": 22.0, "income_tax": 25.0, "appreciation": 2.0, "mortgage_rate": 4.10},
    "GB": {"acquisition_fees": 4.0,  "operating": 20.0, "income_tax": 20.0, "appreciation": 2.5, "mortgage_rate": 5.20},
    "ES": {"acquisition_fees": 10.0, "operating": 22.0, "income_tax": 19.0, "appreciation": 3.0, "mortgage_rate": 3.90},
    "CH": {"acquisition_fees": 4.0,  "operating": 18.0, "income_tax": 22.0, "appreciation": 1.5, "mortgage_rate": 2.40},
    "IT": {"acquisition_fees": 9.0,  "operating": 24.0, "income_tax": 21.0, "appreciation": 1.8, "mortgage_rate": 4.30},
    "AE": {"acquisition_fees": 6.0,  "operating": 18.0, "income_tax": 0.0,  "appreciation": 4.0, "mortgage_rate": 4.99},
    "PT": {"acquisition_fees": 8.0,  "operating": 22.0, "income_tax": 28.0, "appreciation": 3.0, "mortgage_rate": 4.10},
}
DEFAULT_ASSUMPTIONS = {
    "acquisition_fees": 7.0,
    "operating": 22.0,
    "income_tax": 22.0,
    "appreciation": 2.5,
    "mortgage_rate": 4.50,
}


def _f(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


@dataclass(frozen=True)
class SimulatorInputs:
    price: float
    currency: str
    country_code: str
    rental_yield_pct: float
    down_payment_pct: float = 30.0
    mortgage_years: int = 25
    mortgage_rate_pct: float | None = None  # falls back to country
    appreciation_pct: float | None = None   # falls back to country
    horizon_years: int = 10


@dataclass
class CashflowYear:
    year: int
    gross_rent: float
    operating_costs: float
    mortgage_payment: float
    pretax_cashflow: float
    income_tax: float
    net_cashflow: float
    property_value: float
    equity: float


@dataclass
class SimulatorResult:
    inputs: dict[str, Any]
    assumptions: dict[str, float]
    acquisition: dict[str, float]
    financing: dict[str, float]
    annual: dict[str, float]
    projection: list[CashflowYear] = field(default_factory=list)
    summary: dict[str, float] = field(default_factory=dict)
    disclaimers: list[str] = field(default_factory=list)


def _mortgage_payment(principal: float, annual_rate_pct: float, years: int) -> float:
    """Standard French amortization: fixed monthly payment."""
    if principal <= 0 or years <= 0:
        return 0.0
    r = (annual_rate_pct / 100.0) / 12.0
    n = years * 12
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


def _amortization_balance(principal: float, annual_rate_pct: float, years: int, after_years: int) -> float:
    """Outstanding principal after `after_years` of payments."""
    if principal <= 0 or years <= 0:
        return 0.0
    r = (annual_rate_pct / 100.0) / 12.0
    n_total = years * 12
    n_paid = min(after_years, years) * 12
    if r == 0:
        return max(0.0, principal * (1 - n_paid / n_total))
    pmt = _mortgage_payment(principal, annual_rate_pct, years)
    balance = principal * (1 + r) ** n_paid - pmt * ((1 + r) ** n_paid - 1) / r
    return max(0.0, balance)


def simulate(inputs: SimulatorInputs) -> SimulatorResult:
    """Compute a full cashflow projection for a property.

    Outputs are intentionally flat dicts so they serialize directly to the UI
    and to the AI advisor's RAG layer.
    """

    assumptions = COUNTRY_ASSUMPTIONS.get(inputs.country_code, DEFAULT_ASSUMPTIONS).copy()
    if inputs.mortgage_rate_pct is not None:
        assumptions["mortgage_rate"] = float(inputs.mortgage_rate_pct)
    if inputs.appreciation_pct is not None:
        assumptions["appreciation"] = float(inputs.appreciation_pct)

    price = max(0.0, float(inputs.price))
    yield_pct = max(0.0, float(inputs.rental_yield_pct))
    down_pct = max(0.0, min(100.0, float(inputs.down_payment_pct)))
    down_payment = price * down_pct / 100.0
    loan = price - down_payment

    acquisition_fees = price * assumptions["acquisition_fees"] / 100.0
    cash_in = down_payment + acquisition_fees

    # Financing
    monthly_payment = _mortgage_payment(loan, assumptions["mortgage_rate"], inputs.mortgage_years)
    annual_debt_service = monthly_payment * 12

    # Year-1 operating math
    gross_rent = price * yield_pct / 100.0
    operating_costs = gross_rent * assumptions["operating"] / 100.0
    net_operating_income = gross_rent - operating_costs        # NOI (used for cap rate)
    pretax_cashflow = net_operating_income - annual_debt_service
    taxable_income = max(0.0, net_operating_income)
    income_tax = taxable_income * assumptions["income_tax"] / 100.0
    net_cashflow = pretax_cashflow - income_tax

    cap_rate = (net_operating_income / price * 100.0) if price else 0.0
    cash_on_cash = (net_cashflow / cash_in * 100.0) if cash_in else 0.0

    # Multi-year projection (rent grows with inflation ≈ appreciation rate, conservatively).
    annual_growth = assumptions["appreciation"] / 100.0
    projection: list[CashflowYear] = []
    cumulative_net = 0.0
    for year in range(1, inputs.horizon_years + 1):
        gr = gross_rent * ((1 + annual_growth) ** (year - 1))
        op = gr * assumptions["operating"] / 100.0
        noi = gr - op
        pretax = noi - annual_debt_service
        tax = max(0.0, noi) * assumptions["income_tax"] / 100.0
        net = pretax - tax
        property_value = price * ((1 + annual_growth) ** year)
        outstanding = _amortization_balance(loan, assumptions["mortgage_rate"], inputs.mortgage_years, year)
        equity = property_value - outstanding
        cumulative_net += net
        projection.append(CashflowYear(
            year=year,
            gross_rent=round(gr, 2),
            operating_costs=round(op, 2),
            mortgage_payment=round(annual_debt_service, 2),
            pretax_cashflow=round(pretax, 2),
            income_tax=round(tax, 2),
            net_cashflow=round(net, 2),
            property_value=round(property_value, 2),
            equity=round(equity, 2),
        ))

    horizon_value = projection[-1].property_value if projection else price
    horizon_equity = projection[-1].equity if projection else (price - loan)
    total_return = (horizon_equity - cash_in) + cumulative_net
    total_return_pct = (total_return / cash_in * 100.0) if cash_in else 0.0

    disclaimers = [
        f"Country baseline: {inputs.country_code} — operating costs {assumptions['operating']:.0f}% of "
        f"gross rent, income tax {assumptions['income_tax']:.0f}%, capital appreciation "
        f"{assumptions['appreciation']:.1f}%/yr.",
        "Projections assume rent grows at the country appreciation rate. Real-world rent growth will diverge.",
        "Mortgage figures use a constant interest rate for the full term. Re-mortgage events are not modelled.",
        "Excludes capital-gains tax on exit, currency hedging costs and any local property tax over and above the operating buffer.",
    ]

    return SimulatorResult(
        inputs={
            "price": round(price, 2),
            "currency": inputs.currency,
            "country_code": inputs.country_code,
            "rental_yield_pct": yield_pct,
            "down_payment_pct": down_pct,
            "mortgage_years": inputs.mortgage_years,
            "horizon_years": inputs.horizon_years,
        },
        assumptions=assumptions,
        acquisition={
            "price": round(price, 2),
            "down_payment": round(down_payment, 2),
            "acquisition_fees": round(acquisition_fees, 2),
            "loan": round(loan, 2),
            "cash_in": round(cash_in, 2),
        },
        financing={
            "loan": round(loan, 2),
            "rate_pct": assumptions["mortgage_rate"],
            "years": inputs.mortgage_years,
            "monthly_payment": round(monthly_payment, 2),
            "annual_debt_service": round(annual_debt_service, 2),
        },
        annual={
            "gross_rent": round(gross_rent, 2),
            "operating_costs": round(operating_costs, 2),
            "noi": round(net_operating_income, 2),
            "pretax_cashflow": round(pretax_cashflow, 2),
            "income_tax": round(income_tax, 2),
            "net_cashflow": round(net_cashflow, 2),
            "monthly_cashflow": round(net_cashflow / 12.0, 2),
            "cap_rate_pct": round(cap_rate, 2),
            "cash_on_cash_pct": round(cash_on_cash, 2),
        },
        projection=projection,
        summary={
            "horizon_years": inputs.horizon_years,
            "horizon_value": round(horizon_value, 2),
            "horizon_equity": round(horizon_equity, 2),
            "cumulative_net_cashflow": round(cumulative_net, 2),
            "total_return": round(total_return, 2),
            "total_return_pct": round(total_return_pct, 2),
            "annualized_pct": round(((1 + total_return_pct / 100.0) ** (1 / max(1, inputs.horizon_years)) - 1) * 100.0, 2),
        },
        disclaimers=disclaimers,
    )


def simulate_for_property(prop, **overrides: Any) -> SimulatorResult:
    """Convenience wrapper that pulls defaults off a Property + InvestmentMetric.

    Any keyword overrides win over the property's own values (used by HTMX
    re-runs from the UI when the user tweaks a slider).
    """
    metric = getattr(prop, "metric", None)
    yield_default = float(metric.rental_yield) if metric and metric.rental_yield else 4.5

    inputs = SimulatorInputs(
        price=_f(prop.price),
        currency=prop.currency or "EUR",
        country_code=getattr(prop.country, "code", "") or "",
        rental_yield_pct=overrides.get("rental_yield_pct", yield_default),
        down_payment_pct=overrides.get("down_payment_pct", 30.0),
        mortgage_years=int(overrides.get("mortgage_years", 25)),
        mortgage_rate_pct=overrides.get("mortgage_rate_pct"),
        appreciation_pct=overrides.get("appreciation_pct"),
        horizon_years=int(overrides.get("horizon_years", 10)),
    )
    return simulate(inputs)


__all__ = [
    "SimulatorInputs",
    "SimulatorResult",
    "CashflowYear",
    "COUNTRY_ASSUMPTIONS",
    "DEFAULT_ASSUMPTIONS",
    "simulate",
    "simulate_for_property",
]
