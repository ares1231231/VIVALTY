"""Dream-home matchmaker quiz.

A short, shareable quiz that recommends one of our destination countries from a
few lifestyle questions. Pure, ads-safe lifestyle matching — no financial advice.

The scoring is deliberately simple and transparent: each chosen option adds
weights to one or more country codes; the highest total wins. ``budget_eur``
is derived from the budget question so the result view can show on-budget homes.
"""

from __future__ import annotations

QUESTIONS = [
    {
        "id": "climate",
        "prompt": "What's your ideal climate?",
        "options": [
            {"value": "beach", "label": "Sunny beaches all year", "emoji": "🏖️",
             "scores": {"PT": 3, "ES": 3, "AE": 2}},
            {"value": "mediterranean", "label": "Warm Mediterranean", "emoji": "☀️",
             "scores": {"ES": 3, "IT": 3, "PT": 2, "FR": 1}},
            {"value": "seasons", "label": "Four distinct seasons", "emoji": "🍂",
             "scores": {"FR": 3, "GB": 3, "IT": 2, "CH": 2}},
            {"value": "cool", "label": "Cool, crisp & green", "emoji": "🏔️",
             "scores": {"CH": 3, "GB": 2, "FR": 1}},
        ],
    },
    {
        "id": "vibe",
        "prompt": "Which lifestyle calls to you?",
        "options": [
            {"value": "coastal", "label": "Relaxed coastal living", "emoji": "🌊",
             "scores": {"PT": 3, "ES": 2, "IT": 1}},
            {"value": "city", "label": "Buzzing big-city energy", "emoji": "🏙️",
             "scores": {"GB": 3, "AE": 3, "FR": 2, "ES": 1}},
            {"value": "culture", "label": "History, art & culture", "emoji": "🏛️",
             "scores": {"IT": 3, "FR": 3, "ES": 1}},
            {"value": "modern", "label": "Sleek & ultra-modern", "emoji": "✨",
             "scores": {"AE": 3, "CH": 2}},
        ],
    },
    {
        "id": "budget",
        "prompt": "What's your budget?",
        "options": [
            {"value": "u200", "label": "Under €200,000", "emoji": "💶", "budget": 200_000,
             "scores": {"PT": 2, "ES": 3, "IT": 2}},
            {"value": "200_500", "label": "€200k – €500k", "emoji": "💶", "budget": 500_000,
             "scores": {"PT": 2, "ES": 2, "IT": 2, "FR": 1, "AE": 1}},
            {"value": "500_1m", "label": "€500k – €1M", "emoji": "💎", "budget": 1_000_000,
             "scores": {"FR": 2, "GB": 2, "AE": 2, "IT": 1}},
            {"value": "1m_plus", "label": "€1M and above", "emoji": "👑", "budget": 5_000_000,
             "scores": {"CH": 3, "GB": 2, "FR": 2, "AE": 2}},
        ],
    },
    {
        "id": "priority",
        "prompt": "What matters most to you?",
        "options": [
            {"value": "lifestyle", "label": "Sunshine & lifestyle", "emoji": "🌅",
             "scores": {"PT": 3, "ES": 2, "IT": 2}},
            {"value": "career", "label": "Career & connectivity", "emoji": "💼",
             "scores": {"GB": 3, "AE": 2, "CH": 2, "FR": 1}},
            {"value": "value", "label": "Great value for money", "emoji": "🎯",
             "scores": {"ES": 3, "PT": 2, "IT": 2}},
            {"value": "prestige", "label": "Prestige & luxury", "emoji": "🏆",
             "scores": {"CH": 3, "FR": 2, "AE": 2, "GB": 1}},
        ],
    },
    {
        "id": "language",
        "prompt": "How do you feel about language?",
        "options": [
            {"value": "english", "label": "I'd prefer English-speaking", "emoji": "🇬🇧",
             "scores": {"GB": 3, "AE": 2, "PT": 1}},
            {"value": "learn", "label": "Happy to pick up a new one", "emoji": "📚",
             "scores": {"ES": 2, "IT": 2, "PT": 2, "FR": 2}},
            {"value": "multi", "label": "I love a multilingual mix", "emoji": "🌍",
             "scores": {"CH": 3, "FR": 1, "AE": 1}},
        ],
    },
]

# Default budget if the budget question is somehow skipped.
_DEFAULT_BUDGET = 500_000


def score_answers(answers: dict[str, str]) -> tuple[str, int]:
    """Return (winning_country_code, budget_eur) from a {question_id: value} map."""
    totals: dict[str, int] = {}
    budget = _DEFAULT_BUDGET

    by_id = {q["id"]: q for q in QUESTIONS}
    for qid, value in (answers or {}).items():
        question = by_id.get(qid)
        if not question:
            continue
        option = next((o for o in question["options"] if o["value"] == value), None)
        if not option:
            continue
        for code, weight in option.get("scores", {}).items():
            totals[code] = totals.get(code, 0) + weight
        if "budget" in option:
            budget = option["budget"]

    if not totals:
        return "PT", budget
    winner = max(totals.items(), key=lambda kv: kv[1])[0]
    return winner, budget
