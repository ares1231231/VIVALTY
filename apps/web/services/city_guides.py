"""Editorial city-level destination guides (ads-safe SEO landing pages).

Each guide links to a ``geo.City`` row via ``country_code`` + ``city_slug``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from apps.web.services.destinations import GuideFAQ


@dataclass(frozen=True)
class CityGuide:
    country_code: str
    city_slug: str
    name: str
    tagline: str
    meta_description: str
    intro: str
    neighbourhoods: list[tuple[str, str]]
    lifestyle: list[tuple[str, str]]
    buying_tips: list[str]
    faqs: list[GuideFAQ] = field(default_factory=list)
    hero_image: str = ""


_CITY_GUIDES: dict[tuple[str, str], CityGuide] = {
    ("PT", "lisbon"): CityGuide(
        country_code="PT",
        city_slug="lisbon",
        name="Lisbon",
        tagline="Tile-lined hills, Atlantic light and a cosmopolitan capital",
        meta_description=(
            "Living in Lisbon: neighbourhoods, cost of living and buying a home as a foreigner. "
            "Practical guide from Vivalty."
        ),
        intro=(
            "Lisbon blends historic neighbourhoods, river views and a relaxed pace of life with "
            "excellent restaurants, international schools and direct flights across Europe. "
            "From Alfama's winding lanes to modern Parque das Nações, the city offers something "
            "for every buyer — whether you want a pied-à-terre or a family home."
        ),
        neighbourhoods=[
            ("Alfama & Graça", "Historic, authentic and walkable — classic Lisbon charm."),
            ("Príncipe Real", "Leafy, design-forward and popular with expat families."),
            ("Parque das Nações", "Modern waterfront living with parks and the Expo district."),
            ("Cascais & Estoril", "Coastal suburbs 30 minutes west — beaches and golf."),
        ],
        lifestyle=[
            ("Avg. price / m²", "€4,500–€7,500 (varies by district)"),
            ("Climate", "Mild winters, warm dry summers"),
            ("Getting around", "Metro, trams, trains to Sintra & Cascais"),
            ("Best for", "City lovers, retirees, remote workers"),
        ],
        buying_tips=[
            "Get your NIF (Portuguese tax number) before making an offer.",
            "Budget 7–10% on top of the purchase price for taxes and notary fees.",
            "Many buyers use a local lawyer to review the CPCV contract.",
        ],
        faqs=[
            GuideFAQ(
                "Is Lisbon good for families?",
                "Yes — international schools, parks and safe neighbourhoods like Príncipe Real and Cascais are popular with families.",
            ),
            GuideFAQ(
                "Can I buy an apartment in Lisbon as a non-resident?",
                "Yes. There are no restrictions on foreign ownership in Portugal for residential property.",
            ),
        ],
        hero_image="https://images.unsplash.com/photo-1555881400-74d7aca8a582?auto=format&fit=crop&w=1600&q=80",
    ),
    ("ES", "valencia"): CityGuide(
        country_code="ES",
        city_slug="valencia",
        name="Valencia",
        tagline="Mediterranean sunshine, paella and a liveable coastal city",
        meta_description=(
            "Living in Valencia: neighbourhoods, lifestyle and buying property in Spain's "
            "third-largest city — a practical guide from Vivalty."
        ),
        intro=(
            "Valencia offers beach access, a compact historic centre and a lower price point than "
            "Barcelona or Madrid. The Turia gardens, the City of Arts and Sciences and a thriving "
            "food scene make it one of Spain's most balanced cities for international buyers."
        ),
        neighbourhoods=[
            ("El Carmen", "Medieval old town — lively, artistic, central."),
            ("Ruzafa", "Trendy, walkable and full of cafés and boutiques."),
            ("Ciutat Vella", "Historic core with character apartments."),
            ("Patacona & Malvarrosa", "Beachfront living east of the centre."),
        ],
        lifestyle=[
            ("Avg. price / m²", "€2,800–€4,500"),
            ("Climate", "300+ days of sunshine"),
            ("Getting around", "Tram, metro, bike-friendly boulevards"),
            ("Best for", "Beach lovers, families, sun-seekers"),
        ],
        buying_tips=[
            "Obtain your NIE (foreigner ID number) early in the process.",
            "Notary fees and transfer tax (ITP) typically add 10–12%.",
            "Check the community fees (comunidad) for apartments before you offer.",
        ],
        faqs=[
            GuideFAQ(
                "Valencia vs Barcelona — which is better to live in?",
                "Valencia is generally more affordable and relaxed; Barcelona offers a larger international job market. Both are excellent for lifestyle buyers.",
            ),
        ],
        hero_image="https://images.unsplash.com/photo-1562883676-8c7feb83f09b?auto=format&fit=crop&w=1600&q=80",
    ),
    ("AE", "dubai-marina"): CityGuide(
        country_code="AE",
        city_slug="dubai-marina",
        name="Dubai Marina",
        tagline="Skyline towers, yacht clubs and waterfront living",
        meta_description=(
            "Living in Dubai Marina: buying an apartment in Dubai's iconic waterfront district — "
            "neighbourhoods, process and FAQs."
        ),
        intro=(
            "Dubai Marina is one of the UAE's most recognisable addresses — a forest of glass towers "
            "around a man-made canal, with restaurants, beaches and the tram at your doorstep. "
            "Foreign buyers can own freehold apartments here outright."
        ),
        neighbourhoods=[
            ("Marina Walk", "Pedestrian promenade with cafés and marina views."),
            ("JBR (Jumeirah Beach Residence)", "Beach access and resort-style amenities."),
            ("Marina Gate & West", "Newer towers with premium finishes."),
        ],
        lifestyle=[
            ("Avg. price / m²", "AED 1,800–3,500"),
            ("Climate", "Hot summers, warm winters"),
            ("Getting around", "Metro, tram, taxis"),
            ("Best for", "Professionals, investors seeking rental demand, beach lifestyle"),
        ],
        buying_tips=[
            "Confirm the property is in a designated freehold zone.",
            "Review service charges (HOA) — they vary significantly by building.",
            "Transactions are typically fast once the MOU is signed.",
        ],
        faqs=[
            GuideFAQ(
                "Can foreigners buy in Dubai Marina?",
                "Yes — Dubai Marina is a freehold area where non-UAE nationals can own property outright.",
            ),
        ],
        hero_image="https://images.unsplash.com/photo-1512453979798-5ea266f8880c?auto=format&fit=crop&w=1600&q=80",
    ),
    ("FR", "paris"): CityGuide(
        country_code="FR",
        city_slug="paris",
        name="Paris",
        tagline="The world's most storied capital — arrondissements for every taste",
        meta_description=(
            "Living in Paris: arrondissements, buying process and lifestyle guide for "
            "international buyers on Vivalty."
        ),
        intro=(
            "Paris remains one of the world's most desirable cities — culture, cuisine, architecture "
            "and a compact layout that makes every arrondissement feel distinct. From Left Bank "
            "intellectual charm to Right Bank elegance, buyers find everything from Haussmannian "
            "apartments to modern loft conversions."
        ),
        neighbourhoods=[
            ("Le Marais (4th)", "Historic, central, full of galleries and boutiques."),
            ("Saint-Germain (6th)", "Classic Left Bank elegance."),
            ("Montmartre (18th)", "Village feel with Sacré-Cœur views."),
            ("Bastille & Oberkampf (11th)", "Young, creative and more affordable."),
        ],
        lifestyle=[
            ("Avg. price / m²", "€9,000–€14,000 (central arrondissements)"),
            ("Climate", "Four seasons, mild compared to northern Europe"),
            ("Getting around", "Metro, RER, Velib bikes"),
            ("Best for", "Culture lovers, professionals, second-home buyers"),
        ],
        buying_tips=[
            "Engage a notaire early — they handle the legal transfer in France.",
            "Budget ~7–8% in notary fees and taxes on top of the purchase price.",
            "Check co-ownership rules (copropriété) for apartments.",
        ],
        faqs=[
            GuideFAQ(
                "Can Americans and Brits buy in Paris?",
                "Yes — there are no restrictions on foreign ownership of residential property in France.",
            ),
        ],
        hero_image="https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&w=1600&q=80",
    ),
    ("GB", "london"): CityGuide(
        country_code="GB",
        city_slug="london",
        name="London",
        tagline="A global capital of culture, finance and world-class neighbourhoods",
        meta_description=(
            "Living in London: boroughs, buying process and practical guide for international "
            "buyers on Vivalty."
        ),
        intro=(
            "London offers unmatched diversity — from Notting Hill townhouses to Canary Wharf "
            "apartments and Richmond family homes. Strong legal frameworks, excellent schools "
            "and global connectivity make it a perennial favourite for international buyers."
        ),
        neighbourhoods=[
            ("Kensington & Chelsea", "Prestige addresses and museum quarter."),
            ("Canary Wharf", "Modern towers and Docklands lifestyle."),
            ("Richmond & Twickenham", "Green, family-friendly west London."),
            ("Shoreditch", "Creative east London with loft conversions."),
        ],
        lifestyle=[
            ("Avg. price / m²", "£8,000–£15,000+ (varies widely)"),
            ("Climate", "Mild, changeable — four distinct seasons"),
            ("Getting around", "Tube, Overground, national rail"),
            ("Best for", "Professionals, families, global citizens"),
        ],
        buying_tips=[
            "Instruct a solicitor as soon as your offer is accepted.",
            "Budget for Stamp Duty Land Tax (SDLT) — rates vary by price and buyer status.",
            "Leasehold vs freehold matters — check remaining lease length on flats.",
        ],
        faqs=[
            GuideFAQ(
                "Can non-UK residents buy property in London?",
                "Yes — there are no legal restrictions on foreign ownership of residential property in England.",
            ),
        ],
        hero_image="https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?auto=format&fit=crop&w=1600&q=80",
    ),
    ("IT", "milan"): CityGuide(
        country_code="IT",
        city_slug="milan",
        name="Milan",
        tagline="Italy's design capital — fashion, finance and la dolce vita",
        meta_description=(
            "Living in Milan: neighbourhoods, lifestyle and buying a home in Italy's economic "
            "capital — guide for international buyers."
        ),
        intro=(
            "Milan is Italy's business and design hub — efficient, international and surprisingly "
            "liveable. From the Brera art district to the Navigli canals, the city combines "
            "northern European practicality with Italian warmth."
        ),
        neighbourhoods=[
            ("Brera", "Artistic, central, walkable — the classic Milan address."),
            ("Porta Nuova", "Modern towers and the Bosco Verticale."),
            ("Navigli", "Canalside bars and creative energy."),
            ("CityLife", "New development with parks and premium apartments."),
        ],
        lifestyle=[
            ("Avg. price / m²", "€4,500–€7,000"),
            ("Climate", "Hot summers, cool winters, fog in autumn"),
            ("Getting around", "Metro, trams, high-speed rail to Rome & Florence"),
            ("Best for", "Professionals, design lovers, urban lifestyle"),
        ],
        buying_tips=[
            "Obtain your codice fiscale (tax code) before signing.",
            "Notary fees and registration tax typically add 9–12%.",
            "Verify the property's cadastral records with your lawyer.",
        ],
        faqs=[
            GuideFAQ(
                "Is Milan a good base for exploring Italy?",
                "Excellent — high-speed trains reach Florence in under 2 hours and Rome in under 3.",
            ),
        ],
        hero_image="https://images.unsplash.com/photo-1513581166391-887a96ddeafd?auto=format&fit=crop&w=1600&q=80",
    ),
}


def city_guide(country_code: str, city_slug: str) -> CityGuide | None:
    return _CITY_GUIDES.get(((country_code or "").upper(), (city_slug or "").lower()))


def guides_for_country(country_code: str) -> list[CityGuide]:
    code = (country_code or "").upper()
    return [g for (c, _), g in _CITY_GUIDES.items() if c == code]


def all_city_guide_keys() -> list[tuple[str, str]]:
    return list(_CITY_GUIDES.keys())
