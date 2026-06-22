"""Lightweight UI translations for key marketing strings.

Full page content stays in English for SEO; nav/hero CTAs translate for
international ad campaigns. Extend ``STRINGS`` as needed.
"""

from __future__ import annotations

SUPPORTED_LANGUAGES: list[tuple[str, str]] = [
    ("en", "English"),
    ("fr", "Français"),
    ("es", "Español"),
    ("pt", "Português"),
    ("it", "Italiano"),
    ("ar", "العربية"),
]

STRINGS: dict[str, dict[str, str]] = {
    "nav.buy": {
        "en": "Buy",
        "fr": "Acheter",
        "es": "Comprar",
        "pt": "Comprar",
        "it": "Acquista",
        "ar": "شراء",
    },
    "nav.rent": {
        "en": "Rent",
        "fr": "Louer",
        "es": "Alquilar",
        "pt": "Arrendar",
        "it": "Affitta",
        "ar": "إيجار",
    },
    "nav.luxury": {
        "en": "Luxury",
        "fr": "Prestige",
        "es": "Lujo",
        "pt": "Luxo",
        "it": "Lusso",
        "ar": "فاخر",
    },
    "nav.destinations": {
        "en": "Destinations",
        "fr": "Destinations",
        "es": "Destinos",
        "pt": "Destinos",
        "it": "Destinazioni",
        "ar": "الوجهات",
    },
    "nav.quiz": {
        "en": "Find your home",
        "fr": "Trouvez votre maison",
        "es": "Encuentra tu hogar",
        "pt": "Encontre a sua casa",
        "it": "Trova casa",
        "ar": "اعثر على منزلك",
    },
    "nav.explore": {
        "en": "Price explorer",
        "fr": "Comparateur de prix",
        "es": "Explorador de precios",
        "pt": "Explorador de preços",
        "it": "Confronto prezzi",
        "ar": "مقارنة الأسعار",
    },
    "hero.cta.browse": {
        "en": "Browse homes",
        "fr": "Parcourir les biens",
        "es": "Ver propiedades",
        "pt": "Ver imóveis",
        "it": "Sfoglia case",
        "ar": "تصفح العقارات",
    },
    "hero.cta.quiz": {
        "en": "Take the quiz",
        "fr": "Faire le quiz",
        "es": "Hacer el quiz",
        "pt": "Fazer o quiz",
        "it": "Fai il quiz",
        "ar": "ابدأ الاختبار",
    },
    "footer.tagline": {
        "en": "International real estate, beautifully curated.",
        "fr": "Immobilier international, soigneusement sélectionné.",
        "es": "Inmobiliaria internacional, cuidadosamente seleccionada.",
        "pt": "Imobiliário internacional, cuidadosamente selecionado.",
        "it": "Immobiliare internazionale, curato con cura.",
        "ar": "عقارات دولية، مختارة بعناية.",
    },
    "verified.badge": {
        "en": "Verified",
        "fr": "Vérifié",
        "es": "Verificado",
        "pt": "Verificado",
        "it": "Verificato",
        "ar": "موثق",
    },
}


def translate(key: str, lang: str, default: str = "") -> str:
    lang = (lang or "en").split("-")[0].lower()
    bucket = STRINGS.get(key, {})
    if lang in bucket:
        return bucket[lang]
    return bucket.get("en") or default or key


def active_language(request) -> str:
    code = getattr(request, "LANGUAGE_CODE", None) or "en"
    return code.split("-")[0].lower()
