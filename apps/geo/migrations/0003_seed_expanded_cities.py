"""Expand the per-country city catalogue for listing search / filters.

The location step can resolve *any* city via Nominatim, but a richer local
catalogue makes the empty-focus starter list and marketplace filters useful.
"""

from __future__ import annotations

from django.db import migrations
from django.utils.text import slugify

# Names only — market metrics are optional and filled later / left null.
EXPANDED_CITIES: dict[str, list[str]] = {
    "FR": [
        "Aix-en-Provence", "Ajaccio", "Amiens", "Angers", "Annecy", "Antibes",
        "Avignon", "Bayonne", "Brest", "Caen", "Clermont-Ferrand", "Dijon",
        "Grenoble", "La Rochelle", "Le Havre", "Limoges", "Menton", "Metz",
        "Nancy", "Nîmes", "Orléans", "Perpignan", "Poitiers", "Reims",
        "Rennes", "Rouen", "Saint-Étienne", "Toulon", "Tours", "Versailles",
    ],
    "ES": [
        "Almería", "Badajoz", "Burgos", "Cádiz", "Cartagena", "Castellón",
        "Córdoba", "Coruña", "Gijón", "Girona", "Huelva", "Jaén",
        "Las Palmas", "León", "Lleida", "Logroño", "Murcia", "Oviedo",
        "Pamplona", "Salamanca", "Santander", "Santiago de Compostela",
        "Segovia", "Sitges", "Tarragona", "Toledo", "Torrevieja", "Vigo",
        "Vitoria-Gasteiz", "Zaragoza", "Benidorm", "Estepona", "Fuengirola",
        "Torremolinos", "Ronda", "Salou", "Puerto Banús",
    ],
    "PT": [
        "Albufeira", "Aveiro", "Beja", "Castelo Branco", "Évora", "Figueira da Foz",
        "Funchal", "Guimarães", "Leiria", "Óbidos", "Ponta Delgada", "Portimão",
        "Setúbal", "Sintra", "Tavira", "Viana do Castelo", "Vila Nova de Gaia",
        "Viseu", "Almada", "Amadora", "Bragança", "Chaves", "Covilhã",
        "Estoril", "Guarda", "Loule", "Nazaré", "Oeiras", "Póvoa de Varzim",
        "Sesimbra", "Torres Vedras", "Vilamoura",
    ],
    "IT": [
        "Bari", "Bergamo", "Brescia", "Catania", "Livorno", "Lucca",
        "Padua", "Parma", "Perugia", "Pisa", "Rimini", "Siena",
        "Sorrento", "Trieste", "Udine", "Amalfi", "Capri", "Cagliari",
        "Lecce", "Mantua", "Modena", "Positano", "Ravenna", "Reggio Calabria",
        "Sanremo", "Sardinia", "Sicily", "Taormina", "Trento", "Vicenza",
    ],
    "GB": [
        "Aberdeen", "Bath", "Belfast", "Bournemouth", "Cardiff", "Chester",
        "Coventry", "Exeter", "Guildford", "Inverness", "Leicester", "Newcastle",
        "Norwich", "Nottingham", "Plymouth", "Reading", "Sheffield", "Southampton",
        "St Ives", "York", "Canterbury", "Cheltenham", "Cornwall", "Cotswolds",
        "Harrogate", "Milton Keynes", "Portsmouth", "Windsor", "Winchester",
    ],
    "CH": [
        "Arosa", "Chur", "Davos", "Fribourg", "Interlaken", "Locarno",
        "Lucerne", "Neuchâtel", "Sion", "Thun", "Verbier", "Winterthur",
        "Zug", "Andermatt", "Appenzell", "Crans-Montana", "Gstaad",
        "Klosters", "Nyon", "Schaffhausen", "Sierre", "Vevey",
    ],
    "AE": [
        "Al Ain", "Ajman", "Dubai Hills", "Emirates Hills", "Fujairah",
        "Jumeirah", "Jumeirah Beach Residence", "Jumeirah Lake Towers",
        "MBR City", "Meydan", "Motor City", "Palm Jebel Ali",
        "Dubai Silicon Oasis", "Sports City", "The Springs", "Umm Al Quwain",
        "Yas Island", "Saadiyat Island", "Al Reem Island", "Khalifa City",
        "Dubai South", "Town Square", "Damac Hills", "Mudon",
    ],
}


def seed_expanded(apps, schema_editor):
    Country = apps.get_model("geo", "Country")
    City = apps.get_model("geo", "City")

    for code, names in EXPANDED_CITIES.items():
        try:
            country = Country.objects.get(code=code)
        except Country.DoesNotExist:
            continue
        for name in names:
            slug = slugify(name) or name.lower().replace(" ", "-")[:140]
            City.objects.update_or_create(
                country=country,
                slug=slug,
                defaults={"name": name},
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("geo", "0002_seed_more_cities"),
    ]

    operations = [
        migrations.RunPython(seed_expanded, noop_reverse),
    ]
