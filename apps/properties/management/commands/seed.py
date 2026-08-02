"""Idempotent seed command.

Generates a realistic, brokerage-grade catalogue of international listings:
authentic property names, neighbourhood-specific addresses, agency attribution,
unique descriptions and editorial-quality images.

Usage:
    python manage.py seed              # safe to re-run; updates baselines + adds missing items.
    python manage.py seed --reset      # wipes properties first.
"""

from __future__ import annotations

import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.geo.models import City, Country
from apps.properties.models import (
    InvestmentTag,
    Property,
    PropertyImage,
    PropertyType,
)
from apps.properties.services.scoring import upsert_metric
from apps.users.models import Role, User


COUNTRIES = [
    {
        "code": "FR", "name": "France", "currency": "EUR", "flag_emoji": "🇫🇷",
        "base_roi_min": 3.5, "base_roi_max": 6.0, "base_rental_yield": 4.5,
        "base_demand": "high", "base_trend": "stable", "base_risk": "low",
        "summary": "Mature European market. Stable yields in Paris suburbs and growth pockets along the Côte d'Azur and Lyon.",
    },
    {
        "code": "GB", "name": "United Kingdom", "currency": "GBP", "flag_emoji": "🇬🇧",
        "base_roi_min": 3.0, "base_roi_max": 7.0, "base_rental_yield": 5.0,
        "base_demand": "high", "base_trend": "stable", "base_risk": "medium",
        "summary": "Deep liquidity in London; stronger yields in Manchester, Liverpool and Birmingham.",
    },
    {
        "code": "ES", "name": "Spain", "currency": "EUR", "flag_emoji": "🇪🇸",
        "base_roi_min": 4.0, "base_roi_max": 7.5, "base_rental_yield": 5.5,
        "base_demand": "high", "base_trend": "growth", "base_risk": "low",
        "summary": "Tourist demand on the coast and Madrid. Valencia and Málaga show strong growth.",
    },
    {
        "code": "CH", "name": "Switzerland", "currency": "CHF", "flag_emoji": "🇨🇭",
        "base_roi_min": 2.0, "base_roi_max": 4.0, "base_rental_yield": 3.0,
        "base_demand": "medium", "base_trend": "stable", "base_risk": "low",
        "summary": "Capital-preservation market. Low yields, very low risk; strong demand in Geneva and Zurich.",
    },
    {
        "code": "IT", "name": "Italy", "currency": "EUR", "flag_emoji": "🇮🇹",
        "base_roi_min": 3.5, "base_roi_max": 7.0, "base_rental_yield": 4.8,
        "base_demand": "medium", "base_trend": "stable", "base_risk": "medium",
        "summary": "Heterogeneous: Milan and Bologna see steady demand; tourist hotspots (Florence, Rome) yield well in short-let.",
    },
    {
        "code": "AE", "name": "United Arab Emirates", "currency": "AED", "flag_emoji": "🇦🇪",
        "base_roi_min": 6.0, "base_roi_max": 10.0, "base_rental_yield": 7.5,
        "base_demand": "high", "base_trend": "growth", "base_risk": "medium",
        "summary": "High yields in Dubai (Marina, JVC, Business Bay). Tax-free environment; cycle sensitivity to oil and global capital.",
    },
    {
        "code": "PT", "name": "Portugal", "currency": "EUR", "flag_emoji": "🇵🇹",
        "base_roi_min": 4.5, "base_roi_max": 8.0, "base_rental_yield": 5.8,
        "base_demand": "high", "base_trend": "growth", "base_risk": "low",
        "summary": "Lisbon and Porto see strong growth; Algarve is short-let driven. Golden visa changes have shifted demand inland.",
    },
]

CITIES = {
    "FR": [
        {"name": "Paris", "avg_price_sqm": 11500, "avg_rental_yield": 3.5, "demand": "high", "trend": "stable", "risk": "low", "score": 78, "population": 2_140_000},
        {"name": "Lyon", "avg_price_sqm": 5300, "avg_rental_yield": 4.6, "demand": "high", "trend": "growth", "risk": "low", "score": 80, "population": 522_000},
        {"name": "Nice", "avg_price_sqm": 5100, "avg_rental_yield": 4.2, "demand": "high", "trend": "stable", "risk": "low", "score": 76, "population": 342_000},
    ],
    "GB": [
        {"name": "London", "avg_price_sqm": 13500, "avg_rental_yield": 3.8, "demand": "high", "trend": "stable", "risk": "medium", "score": 75, "population": 8_982_000},
        {"name": "Manchester", "avg_price_sqm": 3800, "avg_rental_yield": 6.2, "demand": "high", "trend": "growth", "risk": "low", "score": 86, "population": 552_000},
        {"name": "Birmingham", "avg_price_sqm": 3200, "avg_rental_yield": 5.8, "demand": "medium", "trend": "growth", "risk": "low", "score": 82, "population": 1_141_000},
    ],
    "ES": [
        {"name": "Madrid", "avg_price_sqm": 4400, "avg_rental_yield": 5.0, "demand": "high", "trend": "growth", "risk": "low", "score": 84, "population": 3_223_000},
        {"name": "Barcelona", "avg_price_sqm": 4900, "avg_rental_yield": 4.7, "demand": "high", "trend": "stable", "risk": "low", "score": 81, "population": 1_620_000},
        {"name": "Valencia", "avg_price_sqm": 2400, "avg_rental_yield": 6.4, "demand": "high", "trend": "growth", "risk": "low", "score": 88, "population": 791_000},
        {"name": "Málaga", "avg_price_sqm": 2900, "avg_rental_yield": 6.0, "demand": "high", "trend": "growth", "risk": "low", "score": 85, "population": 578_000},
    ],
    "CH": [
        {"name": "Geneva", "avg_price_sqm": 14500, "avg_rental_yield": 2.9, "demand": "high", "trend": "stable", "risk": "low", "score": 70, "population": 203_000},
        {"name": "Zurich", "avg_price_sqm": 16000, "avg_rental_yield": 2.8, "demand": "high", "trend": "stable", "risk": "low", "score": 72, "population": 421_000},
        {"name": "Lausanne", "avg_price_sqm": 12000, "avg_rental_yield": 3.1, "demand": "medium", "trend": "stable", "risk": "low", "score": 68, "population": 140_000},
    ],
    "IT": [
        {"name": "Milan", "avg_price_sqm": 5200, "avg_rental_yield": 4.5, "demand": "high", "trend": "growth", "risk": "low", "score": 80, "population": 1_396_000},
        {"name": "Rome", "avg_price_sqm": 3500, "avg_rental_yield": 4.8, "demand": "high", "trend": "stable", "risk": "medium", "score": 76, "population": 2_873_000},
        {"name": "Florence", "avg_price_sqm": 4100, "avg_rental_yield": 5.6, "demand": "medium", "trend": "stable", "risk": "low", "score": 78, "population": 367_000},
    ],
    "AE": [
        {"name": "Dubai Marina", "avg_price_sqm": 4800, "avg_rental_yield": 7.8, "demand": "high", "trend": "growth", "risk": "medium", "score": 90, "population": 55_000},
        {"name": "Business Bay", "avg_price_sqm": 4100, "avg_rental_yield": 8.2, "demand": "high", "trend": "growth", "risk": "medium", "score": 88, "population": 30_000},
        {"name": "Jumeirah Village Circle", "avg_price_sqm": 2700, "avg_rental_yield": 9.1, "demand": "high", "trend": "growth", "risk": "medium", "score": 92, "population": 30_000},
        {"name": "Abu Dhabi", "avg_price_sqm": 3300, "avg_rental_yield": 6.5, "demand": "medium", "trend": "stable", "risk": "low", "score": 80, "population": 1_482_000},
    ],
    "PT": [
        {"name": "Lisbon", "avg_price_sqm": 5400, "avg_rental_yield": 5.4, "demand": "high", "trend": "growth", "risk": "low", "score": 86, "population": 545_000},
        {"name": "Porto", "avg_price_sqm": 3300, "avg_rental_yield": 6.1, "demand": "high", "trend": "growth", "risk": "low", "score": 88, "population": 232_000},
        {"name": "Algarve", "avg_price_sqm": 3100, "avg_rental_yield": 6.8, "demand": "high", "trend": "growth", "risk": "low", "score": 84, "population": 467_000},
    ],
}

TAGS = [
    ("High ROI", "emerald"),
    ("Luxury", "amber"),
    ("Emerging market", "sky"),
    ("Short-let friendly", "rose"),
    ("Capital preservation", "indigo"),
    ("New build", "lime"),
    ("Beachfront", "cyan"),
]

# Editorial-grade Unsplash sets per property type — enough variety so a
# 6-card grid never repeats the same hero shot.
IMAGES = {
    "apartment": [
        "https://images.unsplash.com/photo-1505691938895-1758d7feb511?w=1400",
        "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=1400",
        "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=1400",
        "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=1400",
        "https://images.unsplash.com/photo-1574362848149-11496d93a7c7?w=1400",
        "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=1400",
        "https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?w=1400",
    ],
    "studio": [
        "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=1400",
        "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=1400",
        "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=1400",
    ],
    "villa_house": [
        "https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=1400",
        "https://images.unsplash.com/photo-1613490493576-7fde63acd811?w=1400",
        "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=1400",
        "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=1400",
        "https://images.unsplash.com/photo-1572120360610-d971b9d7767c?w=1400",
        "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=1400",
        "https://images.unsplash.com/photo-1580587771525-78b9dba3b914?w=1400",
        "https://images.unsplash.com/photo-1605276374104-dee2a0ed3cd6?w=1400",
    ],
    "commercial": [
        "https://images.unsplash.com/photo-1497366216548-37526070297c?w=1400",
        "https://images.unsplash.com/photo-1497366811353-6870744d04b2?w=1400",
        "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1400",
    ],
    "office": [
        "https://images.unsplash.com/photo-1497366216548-37526070297c?w=1400",
        "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1400",
        "https://images.unsplash.com/photo-1564540583246-934409427776?w=1400",
    ],
    "retail": [
        "https://images.unsplash.com/photo-1604014237800-1c9102c219da?w=1400",
        "https://images.unsplash.com/photo-1556742502-ec7c0e9f34b1?w=1400",
        "https://images.unsplash.com/photo-1552866299-5f02e2eb12bb?w=1400",
    ],
    "land": [
        "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=1400",
        "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=1400",
        "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=1400",
    ],
}

# Authentic neighbourhood + street pairings used to build realistic addresses.
NEIGHBOURHOODS: dict[str, list[tuple[str, list[str]]]] = {
    "Paris": [
        ("Le Marais", ["Rue des Archives", "Rue de Bretagne", "Rue Vieille du Temple"]),
        ("Saint-Germain-des-Prés", ["Rue de Buci", "Rue Bonaparte", "Rue Jacob"]),
        ("Montmartre", ["Rue Lepic", "Rue des Abbesses", "Rue Caulaincourt"]),
        ("Bastille", ["Rue de la Roquette", "Rue Saint-Antoine", "Boulevard Beaumarchais"]),
    ],
    "Lyon": [
        ("Presqu'île", ["Rue de la République", "Rue Mercière", "Place Bellecour"]),
        ("Vieux Lyon", ["Rue Saint-Jean", "Rue du Bœuf", "Montée du Gourguillon"]),
        ("Confluence", ["Quai Rambaud", "Cours Charlemagne", "Place Nautique"]),
    ],
    "Nice": [
        ("Vieux Nice", ["Rue de la Préfecture", "Cours Saleya", "Rue Droite"]),
        ("Promenade des Anglais", ["Promenade des Anglais", "Rue de France", "Boulevard Gambetta"]),
        ("Cimiez", ["Avenue de Cimiez", "Boulevard de Cimiez", "Avenue des Arènes"]),
    ],
    "London": [
        ("Shoreditch", ["Curtain Road", "Old Street", "Great Eastern Street"]),
        ("Kensington", ["Cromwell Road", "Gloucester Road", "Kensington High Street"]),
        ("Canary Wharf", ["Cabot Square", "Westferry Circus", "South Quay"]),
        ("Notting Hill", ["Portobello Road", "Westbourne Park Road", "Ladbroke Grove"]),
    ],
    "Manchester": [
        ("Northern Quarter", ["Stevenson Square", "Tib Street", "Oldham Street"]),
        ("Spinningfields", ["Hardman Square", "Quay Street", "Byrom Street"]),
        ("Ancoats", ["Henry Street", "Cotton Street", "Murray Street"]),
    ],
    "Birmingham": [
        ("Jewellery Quarter", ["Vyse Street", "Frederick Street", "Caroline Street"]),
        ("Digbeth", ["Digbeth High Street", "Floodgate Street", "Heath Mill Lane"]),
        ("Edgbaston", ["Hagley Road", "Wheeleys Road", "Westbourne Road"]),
    ],
    "Madrid": [
        ("Salamanca", ["Calle de Serrano", "Calle de Velázquez", "Calle de Goya"]),
        ("Chamberí", ["Calle de Fuencarral", "Calle de Sagasta", "Calle de Alburquerque"]),
        ("Malasaña", ["Calle del Pez", "Calle del Espíritu Santo", "Calle de la Palma"]),
    ],
    "Barcelona": [
        ("Eixample", ["Carrer de Mallorca", "Passeig de Gràcia", "Carrer de Provença"]),
        ("Gràcia", ["Carrer Gran de Gràcia", "Plaça del Sol", "Carrer de Verdi"]),
        ("Born", ["Passeig del Born", "Carrer de l'Argenteria", "Carrer de Montcada"]),
    ],
    "Valencia": [
        ("Ciutat Vella", ["Carrer de Cavallers", "Carrer dels Serrans", "Plaça del Mercat"]),
        ("Ruzafa", ["Carrer de Cuba", "Carrer de Sueca", "Carrer de Cádiz"]),
        ("El Cabanyal", ["Carrer de la Reina", "Carrer del Doctor Lluch", "Carrer del Progrés"]),
    ],
    "Málaga": [
        ("Centro Histórico", ["Calle Larios", "Calle Granada", "Plaza de la Constitución"]),
        ("Soho", ["Calle Tomás Heredia", "Calle Vendeja", "Calle Casas de Campos"]),
        ("Pedregalejo", ["Avenida Juan Sebastián Elcano", "Paseo Marítimo Pablo Ruiz Picasso", "Calle Bolivia"]),
    ],
    "Geneva": [
        ("Eaux-Vives", ["Rue de la Mairie", "Rue Versonnex", "Rue Adrien-Lachenal"]),
        ("Pâquis", ["Rue de Berne", "Rue du Cendrier", "Rue du Mont-Blanc"]),
        ("Champel", ["Avenue de Champel", "Avenue Krieg", "Chemin Beau-Soleil"]),
    ],
    "Zurich": [
        ("Kreis 1", ["Bahnhofstrasse", "Limmatquai", "Rennweg"]),
        ("Seefeld", ["Seefeldstrasse", "Höschgasse", "Färberstrasse"]),
        ("Wiedikon", ["Birmensdorferstrasse", "Manessestrasse", "Goldbrunnenstrasse"]),
    ],
    "Lausanne": [
        ("Ouchy", ["Avenue d'Ouchy", "Place de la Navigation", "Quai Jean-Pascal Delamuraz"]),
        ("Flon", ["Rue du Grand-Saint-Jean", "Place de l'Europe", "Rue Centrale"]),
    ],
    "Milan": [
        ("Brera", ["Via Brera", "Via Solferino", "Via Fiori Chiari"]),
        ("Navigli", ["Ripa di Porta Ticinese", "Alzaia Naviglio Grande", "Via Vigevano"]),
        ("Porta Nuova", ["Corso Como", "Via Vincenzo Capelli", "Piazza Gae Aulenti"]),
    ],
    "Rome": [
        ("Trastevere", ["Via della Lungaretta", "Piazza di Santa Maria in Trastevere", "Vicolo del Cinque"]),
        ("Prati", ["Via Cola di Rienzo", "Via Crescenzio", "Viale Giulio Cesare"]),
        ("Monti", ["Via dei Serpenti", "Via Panisperna", "Via del Boschetto"]),
    ],
    "Florence": [
        ("Oltrarno", ["Via Maggio", "Borgo San Frediano", "Via dello Sprone"]),
        ("Santa Croce", ["Via dei Neri", "Borgo Santa Croce", "Via dei Benci"]),
        ("San Niccolò", ["Via di San Niccolò", "Via dei Renai", "Lungarno Serristori"]),
    ],
    "Dubai Marina": [
        ("Marina Promenade", ["Marina Walk", "Al Marsa Street", "King Salman Bin Abdulaziz Al Saud Street"]),
        ("JBR", ["The Walk JBR", "Al Mamsha Street", "Murjan Street"]),
    ],
    "Business Bay": [
        ("Downtown-adjacent", ["Marasi Drive", "Al Abraj Street", "Bay Avenue"]),
        ("Executive Towers", ["Executive Towers Boulevard", "Al Abraj Street", "Burj Khalifa Boulevard"]),
    ],
    "Jumeirah Village Circle": [
        ("District 13", ["Hessa Street", "Al Khail Road", "Sheikh Mohammed Bin Zayed Road"]),
        ("District 16", ["Al Khail Road", "Hessa Street", "JVC Mall Road"]),
    ],
    "Abu Dhabi": [
        ("Saadiyat Island", ["Saadiyat Beach Drive", "Al Mariah Avenue", "Al Saadiyat Boulevard"]),
        ("Yas Island", ["Yas Marina Circuit Boulevard", "Al Yas Avenue", "Yas Bay"]),
    ],
    "Lisbon": [
        ("Príncipe Real", ["Rua da Escola Politécnica", "Rua Dom Pedro V", "Praça do Príncipe Real"]),
        ("Alfama", ["Rua de São Tomé", "Largo de Santo Estêvão", "Rua dos Remédios"]),
        ("Chiado", ["Rua Garrett", "Largo do Chiado", "Rua do Carmo"]),
    ],
    "Porto": [
        ("Ribeira", ["Cais da Ribeira", "Rua das Flores", "Rua de Mouzinho da Silveira"]),
        ("Cedofeita", ["Rua de Cedofeita", "Rua do Bonjardim", "Rua de Costa Cabral"]),
        ("Foz do Douro", ["Avenida do Brasil", "Rua de Diu", "Rua do Padrão"]),
    ],
    "Algarve": [
        ("Lagos", ["Rua Cândido dos Reis", "Avenida dos Descobrimentos", "Rua 25 de Abril"]),
        ("Albufeira", ["Rua 5 de Outubro", "Avenida Sá Carneiro", "Rua dos Pescadores"]),
        ("Vilamoura", ["Marina de Vilamoura", "Avenida Tivoli", "Rua das Acácias"]),
    ],
}

AGENCIES = [
    "Vivalty Premium",
    "Knight & Sterling Realty",
    "Costa Verde Properties",
    "Atlas Mediterranean Estates",
    "London Bridge Investments",
    "Iberia Capital Real Estate",
    "Helvetia Private Estates",
    "Lusitania Estate Partners",
    "Emirates Crown Real Estate",
    "Riviera Estates Group",
]

# Type-aware copywriting templates. {n} refers to the listing index per city.
TITLE_TEMPLATES = {
    "apartment": [
        "{br}-bed apartment, {neighbourhood}",
        "Renovated {br}-bedroom flat overlooking {neighbourhood}",
        "Bright pied-à-terre in {neighbourhood}",
        "Boutique residence in {neighbourhood}",
        "Penthouse-style apartment, {neighbourhood}",
    ],
    "studio": [
        "Bright studio apartment, {neighbourhood}",
        "Compact studio in {neighbourhood}",
        "City-centre studio, {neighbourhood}",
    ],
    "villa_house": [
        "Private villa with garden, {neighbourhood}",
        "Architect-designed villa in {neighbourhood}",
        "Sea-facing villa in {neighbourhood}",
        "Family villa with pool, {neighbourhood}",
        "Townhouse in {neighbourhood}",
        "Family home, {neighbourhood}",
        "Period house in {neighbourhood}",
    ],
    "commercial": [
        "Mixed-use building in {neighbourhood}",
        "High-street commercial unit, {neighbourhood}",
    ],
    "office": [
        "Class-A office floor, {neighbourhood}",
        "Boutique office space, {neighbourhood}",
    ],
    "retail": [
        "Retail unit on {neighbourhood}",
        "Flagship street-level retail, {neighbourhood}",
    ],
    "land": [
        "Development plot, {neighbourhood}",
    ],
}

DESCRIPTION_PARTS = {
    "common": [
        "Move-in-ready condition with high-end finishes throughout.",
        "Tenant-in-place with steady rental history; investor-ready transaction.",
        "Low body-corporate / management fees relative to comparable stock.",
        "Walking distance to public transport, schools and lifestyle amenities.",
        "Recently refurbished with energy-efficient glazing and appliances.",
        "Strategic asset for income-focused or buy-to-let portfolios.",
    ],
    "apartment": [
        "Open-plan living, modern kitchen and a private balcony with city views.",
        "Concierge building with secure parking and a residents' fitness suite.",
        "Light-filled south-facing aspect with double-glazed windows throughout.",
        "Full short-let permission in place — strong Airbnb / corporate-let track record.",
    ],
    "studio": [
        "Efficient open-plan layout with built-in storage and a fitted kitchenette.",
        "Ideal pied-à-terre or first investment — low carrying costs, strong tenant demand.",
    ],
    "villa_house": [
        "Generous outdoor terraces, mature gardens and a heated pool.",
        "Bespoke kitchen, en-suite bedrooms and a dedicated home-office.",
        "Walled grounds with secure gated access and EV charging.",
        "Period features, fireplaces and high ceilings paired with a contemporary fit-out.",
        "Family-friendly layout with separate utility room and rear garden.",
    ],
    "commercial": [
        "Triple-net lease available with a creditworthy occupier.",
        "Strong footfall location with passing traffic supporting valuation upside.",
    ],
    "office": [
        "Open floor plate with raised flooring and column-free office grid.",
        "Flexible terms with the option of a sale-and-leaseback structure.",
    ],
    "retail": [
        "Long unexpired lease term with index-linked rental uplifts.",
        "Adjacent to flagship anchors driving strong daily footfall.",
    ],
    "land": [
        "Outline planning supports a multi-unit residential or mixed-use development.",
        "Ready-to-build site with services to the boundary.",
    ],
}


PROPERTY_TYPES_BY_COUNTRY = {
    "FR": [PropertyType.APARTMENT, PropertyType.APARTMENT, PropertyType.STUDIO, PropertyType.VILLA_HOUSE],
    "GB": [PropertyType.APARTMENT, PropertyType.VILLA_HOUSE, PropertyType.VILLA_HOUSE, PropertyType.COMMERCIAL],
    "ES": [PropertyType.APARTMENT, PropertyType.APARTMENT, PropertyType.VILLA_HOUSE, PropertyType.RETAIL],
    "CH": [PropertyType.APARTMENT, PropertyType.STUDIO, PropertyType.OFFICE],
    "IT": [PropertyType.APARTMENT, PropertyType.APARTMENT, PropertyType.VILLA_HOUSE, PropertyType.COMMERCIAL],
    "AE": [PropertyType.APARTMENT, PropertyType.APARTMENT, PropertyType.VILLA_HOUSE, PropertyType.OFFICE],
    "PT": [PropertyType.APARTMENT, PropertyType.STUDIO, PropertyType.VILLA_HOUSE, PropertyType.VILLA_HOUSE],
}


class Command(BaseCommand):
    help = "Seed Vivalty with target countries, cities, tags and realistic listings."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--reset", action="store_true", help="Delete existing properties first.")
        parser.add_argument("--per-city", type=int, default=3, help="Listings per city.")

    @transaction.atomic
    def handle(self, *args, reset: bool = False, per_city: int = 3, **options):
        random.seed(2026)

        if reset:
            self.stdout.write(self.style.WARNING("Wiping existing Property rows..."))
            Property.objects.all().delete()

        # ── Owner ────────────────────────────────────────────────────────────
        owner, created = User.objects.get_or_create(
            email="demo-owner@vivalty.app",
            defaults={
                "username": "demo-owner@vivalty.app",
                "first_name": "Demo",
                "last_name": "Owner",
                "role": Role.OWNER,
                "company_name": "Vivalty Premium",
            },
        )
        if created:
            owner.set_password("vivalty-demo-pass")
            owner.save()
            self.stdout.write(self.style.SUCCESS(
                "Created demo owner: demo-owner@vivalty.app / vivalty-demo-pass"
            ))

        # ── Tags ─────────────────────────────────────────────────────────────
        tag_objs: dict[str, InvestmentTag] = {}
        for name, color in TAGS:
            tag, _ = InvestmentTag.objects.update_or_create(
                slug=slugify(name), defaults={"name": name, "color": color}
            )
            tag_objs[tag.slug] = tag

        # ── Countries + cities ───────────────────────────────────────────────
        country_objs: dict[str, Country] = {}
        for c in COUNTRIES:
            obj, _ = Country.objects.update_or_create(
                code=c["code"],
                defaults={
                    "name": c["name"],
                    "currency": c["currency"],
                    "flag_emoji": c["flag_emoji"],
                    "base_roi_min": c["base_roi_min"],
                    "base_roi_max": c["base_roi_max"],
                    "base_rental_yield": c["base_rental_yield"],
                    "base_demand": c["base_demand"],
                    "base_trend": c["base_trend"],
                    "base_risk": c["base_risk"],
                    "summary": c["summary"],
                },
            )
            country_objs[c["code"]] = obj

        city_objs: list[City] = []
        for code, cities in CITIES.items():
            country = country_objs[code]
            for city in cities:
                obj, _ = City.objects.update_or_create(
                    country=country, slug=slugify(city["name"]),
                    defaults={
                        "name": city["name"],
                        "population": city["population"],
                        "avg_price_sqm": Decimal(str(city["avg_price_sqm"])),
                        "avg_rental_yield": Decimal(str(city["avg_rental_yield"])),
                        "demand": city["demand"],
                        "trend": city["trend"],
                        "risk": city["risk"],
                        "investment_score": city["score"],
                        "summary": (
                            f"{city['name']} — avg €/m² {city['avg_price_sqm']}, "
                            f"yield {city['avg_rental_yield']}%, score {city['score']}/100."
                        ),
                    },
                )
                city_objs.append(obj)

        # ── Properties ────────────────────────────────────────────────────────
        added = 0
        for city in city_objs:
            country = city.country
            type_pool = PROPERTY_TYPES_BY_COUNTRY.get(country.code, [PropertyType.APARTMENT])
            for i in range(per_city):
                ptype = random.choice(type_pool)
                if ptype == PropertyType.STUDIO:
                    br = 0
                elif ptype not in (PropertyType.COMMERCIAL, PropertyType.OFFICE, PropertyType.LAND, PropertyType.RETAIL):
                    br = random.choice([1, 2, 3, 4])
                else:
                    br = None
                area = round(random.uniform(48, 320), 1)
                psqm = float(city.avg_price_sqm or 3000)
                price = round(area * psqm * random.uniform(0.85, 1.30), -2)

                # Realistic neighbourhood + street
                pool = NEIGHBOURHOODS.get(city.name, [(city.name, [f"{city.name} High Street"])])
                neighbourhood, streets = random.choice(pool)
                street = random.choice(streets)
                house_no = random.randint(2, 220)
                address = f"{house_no} {street}, {neighbourhood}, {city.name}"

                # Title (de-duplicated by suffix when collisions occur)
                title_tpl = random.choice(TITLE_TEMPLATES.get(ptype, TITLE_TEMPLATES["apartment"]))
                title = title_tpl.format(br=br or "open-plan", neighbourhood=neighbourhood)
                if Property.objects.filter(title=title, city=city).exists():
                    title = f"{title} · Ref {random.randint(1000, 9999)}"
                if Property.objects.filter(title=title, city=city).exists():
                    continue

                # Description — type-specific + 2 universal flavour lines
                base = random.choice(DESCRIPTION_PARTS.get(ptype, DESCRIPTION_PARTS["apartment"]))
                seasoning = random.sample(DESCRIPTION_PARTS["common"], k=2)
                desc_intro = (
                    f"{('Luxury' if psqm > 9000 else 'Smart')} investment opportunity in "
                    f"{neighbourhood}, {city.name}, comprising "
                    f"{('an open-plan' if not br else f'{br}-bedroom')} "
                    f"{ptype.label.lower()} of {area:.0f} m². "
                )
                desc = desc_intro + " ".join([base] + seasoning)

                listing_ref = f"VVT-{country.code}-{city.id:03d}-{(Property.objects.filter(city=city).count() + 1):03d}"
                agency = random.choice(AGENCIES) if random.random() > 0.15 else "Vivalty Premium"

                contact_first = random.choice([
                    "Sophie", "James", "Léa", "Alessandro", "Sara",
                    "Mateus", "Hassan", "Olivia", "Lucas", "Clara",
                ])
                contact_last = random.choice([
                    "Laurent", "Whitfield", "García", "Conti", "Almeida",
                    "Müller", "Khan", "Costa", "Beaumont", "Rossi",
                ])
                contact_phone = "+1 555 " + str(random.randint(1000, 9999))

                prop = Property.objects.create(
                    owner=owner,
                    title=title,
                    description=desc,
                    property_type=ptype,
                    status="active",
                    price=Decimal(str(price)),
                    currency=country.currency,
                    country=country,
                    city=city,
                    address=address,
                    bedrooms=br,
                    bathrooms=random.choice([1, 2, 3]) if br else None,
                    area_sqm=Decimal(str(area)),
                    year_built=random.randint(1985, 2025),
                    contact_name=f"{contact_first} {contact_last}",
                    contact_email=f"{contact_first.lower()}.{contact_last.lower()}@{slugify(agency)}.com",
                    contact_phone=contact_phone,
                    listing_agency=agency,
                    listing_ref=listing_ref,
                    is_featured=(i == 0 and random.random() < 0.5),
                    is_premium=(random.random() < 0.18),
                )

                # Images — type-specific gallery
                pool_imgs = IMAGES.get(ptype, IMAGES["apartment"])
                k = min(4, len(pool_imgs))
                for j, url in enumerate(random.sample(pool_imgs, k=k)):
                    PropertyImage.objects.create(property=prop, url=url, position=j)

                # Tags
                slugs: list[str] = []
                if (city.investment_score or 0) >= 85:
                    slugs.append("high-roi")
                if "Dubai" in city.name or psqm < 3500:
                    slugs.append("emerging-market")
                if psqm > 9000:
                    slugs.append("luxury")
                if country.code == "PT" or "Algarve" in city.name or "Marina" in city.name:
                    slugs.append("short-let-friendly")
                if country.code == "CH":
                    slugs.append("capital-preservation")
                if prop.year_built and prop.year_built >= 2020:
                    slugs.append("new-build")
                if "Algarve" in city.name or "Nice" in city.name or "JBR" in neighbourhood:
                    slugs.append("beachfront")
                prop.tags.set(InvestmentTag.objects.filter(slug__in=slugs))

                # Compute & persist explainable score
                upsert_metric(prop)
                added += 1

        # Make sure existing rows (not just new ones) all have an up-to-date
        # investment metric — this matters when the user re-runs `seed` after
        # tweaking weight tables.
        for prop in Property.objects.select_related("city", "country").iterator():
            if not getattr(prop, "metric", None) or not prop.metric.score_breakdown:
                upsert_metric(prop)

        self.stdout.write(self.style.SUCCESS(
            f"Seed complete: {len(country_objs)} countries, {len(city_objs)} cities, "
            f"{added} new properties (total: {Property.objects.count()})."
        ))
