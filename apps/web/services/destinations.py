"""Curated destination-guide content.

These are editorial, *ads-safe* guides (no ROI/yield/investment language) used to
power the `/destinations/` SEO pages. Keeping the long-form copy here — rather
than in the database — lets us ship rich, hand-written content without a
migration, while still joining against live ``Country`` / ``City`` rows and
real listings at render time.

Each entry is keyed by the ISO country code that already exists in ``geo.Country``.
Add a new key here and the destination page lights up automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GuideFAQ:
    question: str
    answer: str


@dataclass(frozen=True)
class DestinationGuide:
    slug: str
    code: str
    name: str
    tagline: str
    # 1-2 sentence meta description (<=160 chars ideally) for SEO.
    meta_description: str
    # Long-form intro paragraph(s).
    intro: str
    # Short bullet "why people buy here" highlights.
    highlights: list[str]
    # Cost-of-living / lifestyle notes (label, value) pairs.
    lifestyle: list[tuple[str, str]]
    # Buying-process steps for a foreign buyer.
    buying_steps: list[tuple[str, str]]
    # FAQ entries (great for SEO + FAQ JSON-LD).
    faqs: list[GuideFAQ] = field(default_factory=list)
    # Hero image (Unsplash, royalty-free) used when no listing photo is available.
    hero_image: str = ""


# ── Guide content ────────────────────────────────────────────────────────────

_GUIDES: dict[str, DestinationGuide] = {
    "PT": DestinationGuide(
        slug="portugal",
        code="PT",
        name="Portugal",
        tagline="Sun, soul and some of Europe's most liveable cities",
        meta_description=(
            "Buying a home in Portugal as a foreigner: Lisbon, Porto and the Algarve "
            "explained — cost of living, neighbourhoods, the buying process and FAQs."
        ),
        intro=(
            "Portugal pairs 300 days of sunshine with a relaxed Atlantic lifestyle, "
            "excellent healthcare and some of the friendliest communities in Europe. "
            "From the tiled streets of Lisbon and the riverside cellars of Porto to the "
            "golden beaches of the Algarve, it's one of the most popular destinations for "
            "international buyers looking for a second home or a fresh start abroad."
        ),
        highlights=[
            "English widely spoken in cities and coastal areas",
            "Mild, sunny climate year-round",
            "Safe, welcoming and easy to settle into",
            "Fast trains and short flights across Europe",
            "Rich food, wine and café culture",
        ],
        lifestyle=[
            ("Climate", "Mild winters, warm dry summers"),
            ("Language", "Portuguese (English common in cities)"),
            ("Currency", "Euro (€)"),
            ("Best for", "Coastal living, city life, retirees & families"),
        ],
        buying_steps=[
            ("Get your NIF", "Apply for a Portuguese tax number (NIF) — required to buy property or open a bank account."),
            ("Open a local bank account", "Most buyers set up a Portuguese account to handle the deposit and ongoing bills."),
            ("Reserve & sign the promissory contract", "A reservation secures the home; the CPCV promissory contract sets the terms and deposit."),
            ("Final deed (Escritura)", "Sign the deed before a notary, pay the balance and transfer taxes, and collect the keys."),
        ],
        faqs=[
            GuideFAQ("Can foreigners buy property in Portugal?",
                     "Yes. There are no restrictions on foreigners buying residential property in Portugal."),
            GuideFAQ("Where do most international buyers look?",
                     "Lisbon, Porto and the Algarve are the most popular, with Lisbon and Porto loved for city life and the Algarve for the coast."),
            GuideFAQ("Do I need to speak Portuguese?",
                     "It helps, but English is widely spoken in cities and coastal regions, and agents and lawyers commonly work in English."),
        ],
        hero_image="https://images.unsplash.com/photo-1555881400-74d7acaacd8b?auto=format&fit=crop&w=1600&q=80",
    ),
    "ES": DestinationGuide(
        slug="spain",
        code="ES",
        name="Spain",
        tagline="Beaches, big cities and an unbeatable outdoor lifestyle",
        meta_description=(
            "Buying a home in Spain as a foreigner: Madrid, Barcelona, Valencia and Málaga "
            "— cost of living, neighbourhoods, the buying process and FAQs."
        ),
        intro=(
            "Spain offers everything from buzzing capital-city life in Madrid to the "
            "Mediterranean charm of Barcelona, Valencia and the Costa del Sol. With long "
            "sunny days, world-class food and a famously social culture, it's a perennial "
            "favourite for buyers seeking a holiday home, a coastal base or a permanent move."
        ),
        highlights=[
            "Vibrant coastal and city living",
            "Excellent value outside the prime centres",
            "World-class food, festivals and nightlife",
            "Great flight connections across the world",
            "Large, welcoming expat communities",
        ],
        lifestyle=[
            ("Climate", "Warm Mediterranean; hot summers"),
            ("Language", "Spanish (regional languages too)"),
            ("Currency", "Euro (€)"),
            ("Best for", "Beach life, city culture, families"),
        ],
        buying_steps=[
            ("Get your NIE", "Apply for a foreigner identification number (NIE) — needed for any property purchase."),
            ("Open a Spanish bank account", "Used for the deposit, taxes and utility payments."),
            ("Sign the reservation & deposit contract", "A reservation takes the home off the market; the contrato de arras sets terms and a deposit."),
            ("Complete before a notary", "Sign the escritura pública, pay the balance and transfer taxes, and register the title."),
        ],
        faqs=[
            GuideFAQ("Can foreigners buy property in Spain?",
                     "Yes. Non-residents can freely buy property; you'll just need an NIE number to complete."),
            GuideFAQ("Which areas are most popular with buyers?",
                     "Madrid and Barcelona for city living, and Valencia, Málaga and the Costa del Sol for coastal homes."),
            GuideFAQ("What extra costs should I budget for?",
                     "Beyond the price, allow roughly 10–13% for transfer tax, notary, registration and legal fees."),
        ],
        hero_image="https://images.unsplash.com/photo-1583422409516-2895a77efded?auto=format&fit=crop&w=1600&q=80",
    ),
    "FR": DestinationGuide(
        slug="france",
        code="FR",
        name="France",
        tagline="Timeless cities, the Riviera and the art of living well",
        meta_description=(
            "Buying a home in France as a foreigner: Paris, Lyon and the Côte d'Azur — "
            "cost of living, neighbourhoods, the buying process and FAQs."
        ),
        intro=(
            "France blends grand-boulevard elegance with alpine villages, vineyards and "
            "the glamour of the Riviera. Whether it's a Paris apartment, a townhouse in "
            "Lyon or a sun-washed villa near Nice, France remains one of the world's most "
            "desirable places to own a home — and the buying process is well-protected for buyers."
        ),
        highlights=[
            "Iconic cities and beautiful countryside",
            "Strong legal protections for buyers",
            "Superb food, wine and culture",
            "Fast TGV trains across the country",
            "World-class healthcare",
        ],
        lifestyle=[
            ("Climate", "Temperate north; Mediterranean south"),
            ("Language", "French"),
            ("Currency", "Euro (€)"),
            ("Best for", "City life, the Riviera, countryside escapes"),
        ],
        buying_steps=[
            ("Make an offer & sign the compromis", "The compromis de vente is a binding preliminary contract with a deposit, usually ~10%."),
            ("Cooling-off period", "Buyers get a 10-day cooling-off period after signing the preliminary contract."),
            ("Notaire handles the legal work", "A government-appointed notaire carries out checks and holds funds securely."),
            ("Final deed (Acte de vente)", "Sign the acte authentique before the notaire, pay the balance and collect the keys."),
        ],
        faqs=[
            GuideFAQ("Can foreigners buy property in France?",
                     "Yes. There are no restrictions on foreign nationals buying property in France."),
            GuideFAQ("What is a notaire?",
                     "A notaire is a public official who handles the legal transfer, due-diligence checks and taxes — protecting both sides."),
            GuideFAQ("How much are buying costs?",
                     "Notaire fees and taxes typically add around 7–8% on older properties (less on new-builds)."),
        ],
        hero_image="https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&w=1600&q=80",
    ),
    "IT": DestinationGuide(
        slug="italy",
        code="IT",
        name="Italy",
        tagline="La dolce vita — from Milan style to Tuscan hills",
        meta_description=(
            "Buying a home in Italy as a foreigner: Milan, Rome and Florence — cost of "
            "living, neighbourhoods, the buying process and FAQs."
        ),
        intro=(
            "Italy is design, history and food woven into daily life. Live the fashion-capital "
            "pace of Milan, the open-air museum of Rome, or the renaissance calm of Florence and "
            "Tuscany. For many buyers, owning a home in Italy is as much about lifestyle as it is "
            "about the building itself."
        ),
        highlights=[
            "Unmatched history, art and architecture",
            "Incredible regional food and wine",
            "Charming towns at gentle prices",
            "Central Mediterranean location",
            "Strong sense of community",
        ],
        lifestyle=[
            ("Climate", "Alpine north; Mediterranean south"),
            ("Language", "Italian"),
            ("Currency", "Euro (€)"),
            ("Best for", "Culture, cuisine, historic homes"),
        ],
        buying_steps=[
            ("Make a formal offer (Proposta)", "A written, signed offer with a small deposit reserves the property."),
            ("Preliminary contract (Compromesso)", "The compromesso sets terms, completion date and a larger deposit."),
            ("Due diligence via a notaio", "A notaio verifies title, planning and any charges on the property."),
            ("Final deed (Rogito)", "Sign the rogito before the notaio, pay the balance and transfer taxes."),
        ],
        faqs=[
            GuideFAQ("Can foreigners buy property in Italy?",
                     "Yes. EU citizens and most non-EU nationals can buy property in Italy (reciprocity rules apply to some countries)."),
            GuideFAQ("What is a codice fiscale?",
                     "It's an Italian tax code, required to buy property, open a bank account and pay utilities."),
            GuideFAQ("Which cities are most popular with buyers?",
                     "Milan for business and design, Rome for history, and Florence and Tuscany for lifestyle homes."),
        ],
        hero_image="https://images.unsplash.com/photo-1516483638261-f4dbaf036963?auto=format&fit=crop&w=1600&q=80",
    ),
    "GB": DestinationGuide(
        slug="united-kingdom",
        code="GB",
        name="United Kingdom",
        tagline="Global cities, green countryside and deep heritage",
        meta_description=(
            "Buying a home in the UK as a foreigner: London, Manchester and Birmingham — "
            "cost of living, neighbourhoods, the buying process and FAQs."
        ),
        intro=(
            "The United Kingdom combines world-leading cities with rolling countryside and "
            "centuries of heritage. London is a true global capital, while Manchester and "
            "Birmingham offer vibrant, fast-growing alternatives. The market is transparent "
            "and well-regulated, making it a reassuring place for international buyers."
        ),
        highlights=[
            "Transparent, well-regulated market",
            "World-class universities and culture",
            "Excellent transport and connectivity",
            "English-speaking and easy to navigate",
            "Diverse, international communities",
        ],
        lifestyle=[
            ("Climate", "Mild, temperate, changeable"),
            ("Language", "English"),
            ("Currency", "Pound sterling (£)"),
            ("Best for", "City careers, students, culture"),
        ],
        buying_steps=[
            ("Make an offer through the agent", "Offers are made via the estate agent; nothing is binding until exchange of contracts."),
            ("Instruct a solicitor", "Your solicitor (conveyancer) runs searches, checks the title and handles contracts."),
            ("Survey & exchange", "Arrange a survey, then exchange contracts with a deposit — the sale becomes binding."),
            ("Completion", "On completion the balance is paid, the title transfers and you get the keys."),
        ],
        faqs=[
            GuideFAQ("Can foreigners buy property in the UK?",
                     "Yes. There are no restrictions on overseas buyers purchasing property in the UK."),
            GuideFAQ("What is the difference between freehold and leasehold?",
                     "Freehold means you own the building and land outright; leasehold means you own the property for a fixed term, common for flats."),
            GuideFAQ("What extra costs apply?",
                     "Budget for Stamp Duty Land Tax, solicitor fees and survey costs on top of the purchase price."),
        ],
        hero_image="https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?auto=format&fit=crop&w=1600&q=80",
    ),
    "CH": DestinationGuide(
        slug="switzerland",
        code="CH",
        name="Switzerland",
        tagline="Alpine quality of life and pristine cities",
        meta_description=(
            "Buying a home in Switzerland as a foreigner: Geneva, Zurich and Lausanne — "
            "cost of living, neighbourhoods, the buying process and FAQs."
        ),
        intro=(
            "Switzerland is a byword for quality of life: spotless cities, dramatic alpine "
            "scenery, superb infrastructure and exceptional safety. From cosmopolitan Geneva "
            "and Zurich to lakeside Lausanne, it appeals to buyers who value stability, nature "
            "and a refined, well-organised way of living."
        ),
        highlights=[
            "Exceptional safety and cleanliness",
            "Stunning lakes and mountains",
            "World-class infrastructure",
            "Central European location",
            "Multilingual, international culture",
        ],
        lifestyle=[
            ("Climate", "Cool alpine; warm lakeside summers"),
            ("Language", "German, French, Italian"),
            ("Currency", "Swiss franc (CHF)"),
            ("Best for", "Quality of life, nature, families"),
        ],
        buying_steps=[
            ("Check eligibility (Lex Koller)", "Foreign buyers may need a permit; rules vary by canton and property type, so confirm early."),
            ("Reserve the property", "A reservation agreement and deposit secure the home while paperwork is prepared."),
            ("Notary prepares the deed", "A public notary drafts the purchase deed and handles the land-registry process."),
            ("Sign & register", "Sign before the notary, pay the balance and register the transfer with the land registry."),
        ],
        faqs=[
            GuideFAQ("Can foreigners buy property in Switzerland?",
                     "Sometimes with conditions. The Lex Koller law can require a permit for non-residents — rules vary by canton, so always check first."),
            GuideFAQ("Which cities are most popular?",
                     "Geneva and Zurich for international careers, and Lausanne for a relaxed lakeside lifestyle."),
            GuideFAQ("Is Switzerland expensive?",
                     "Switzerland has a higher cost of living, balanced by high incomes, excellent services and strong stability."),
        ],
        hero_image="https://images.unsplash.com/photo-1530122037265-a5f1f91d3b99?auto=format&fit=crop&w=1600&q=80",
    ),
    "AE": DestinationGuide(
        slug="uae",
        code="AE",
        name="United Arab Emirates",
        tagline="Modern living, sunshine and a global crossroads",
        meta_description=(
            "Buying a home in Dubai & the UAE as a foreigner: Dubai Marina, Business Bay and "
            "Abu Dhabi — cost of living, neighbourhoods, the buying process and FAQs."
        ),
        intro=(
            "The UAE — led by Dubai and Abu Dhabi — is one of the world's most dynamic places "
            "to live: year-round sunshine, futuristic architecture, world-class amenities and a "
            "truly global community. Designated freehold areas let foreign buyers own homes "
            "outright, and the buying process is fast and digital."
        ),
        highlights=[
            "Year-round sunshine and beaches",
            "Tax-friendly, business-oriented environment",
            "Ultra-modern amenities and safety",
            "A global hub between East and West",
            "Fast, digital property transactions",
        ],
        lifestyle=[
            ("Climate", "Hot desert; warm winters"),
            ("Language", "Arabic (English widely used)"),
            ("Currency", "UAE dirham (AED)"),
            ("Best for", "Modern living, professionals, families"),
        ],
        buying_steps=[
            ("Choose a freehold area", "Foreign buyers can own freehold in designated zones such as Dubai Marina and Business Bay."),
            ("Sign the MOU (Form F)", "Buyer and seller sign a Memorandum of Understanding and the buyer pays a deposit (often 10%)."),
            ("No-objection certificate", "The developer issues an NOC confirming there are no outstanding charges on the property."),
            ("Transfer at the land department", "Both parties complete the transfer at the Land Department and the title deed is issued."),
        ],
        faqs=[
            GuideFAQ("Can foreigners buy property in Dubai?",
                     "Yes. Foreign nationals can buy freehold property in designated areas of Dubai and across the UAE."),
            GuideFAQ("Which areas are most popular with buyers?",
                     "Dubai Marina, Business Bay and Jumeirah Village Circle in Dubai, plus growing areas of Abu Dhabi."),
            GuideFAQ("How fast is the buying process?",
                     "Transactions are largely digital and can complete in a matter of weeks once terms are agreed."),
        ],
        hero_image="https://images.unsplash.com/photo-1512453979798-5ea266f8880c?auto=format&fit=crop&w=1600&q=80",
    ),
}

# slug → code lookup, derived once.
_SLUG_TO_CODE = {g.slug: code for code, g in _GUIDES.items()}


def all_guides() -> list[DestinationGuide]:
    """Guides in a friendly display order."""
    order = ["PT", "ES", "FR", "IT", "GB", "AE", "CH"]
    return [_GUIDES[c] for c in order if c in _GUIDES]


def guide_by_slug(slug: str) -> DestinationGuide | None:
    code = _SLUG_TO_CODE.get((slug or "").lower())
    return _GUIDES.get(code) if code else None


def guide_by_code(code: str) -> DestinationGuide | None:
    return _GUIDES.get((code or "").upper())


def guide_slugs() -> list[str]:
    return [g.slug for g in all_guides()]
