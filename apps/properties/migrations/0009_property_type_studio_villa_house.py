"""Merge villa+house → villa_house, add studio."""

from django.db import migrations, models


def merge_villa_house(apps, schema_editor):
    Property = apps.get_model("properties", "Property")
    Property.objects.filter(property_type__in=["villa", "house"]).update(
        property_type="villa_house"
    )


def split_villa_house(apps, schema_editor):
    """Reverse: map villa_house back to house (best-effort)."""
    Property = apps.get_model("properties", "Property")
    Property.objects.filter(property_type="villa_house").update(property_type="house")
    Property.objects.filter(property_type="studio").update(property_type="apartment")


class Migration(migrations.Migration):

    dependencies = [
        ("properties", "0008_property_featured_until"),
    ]

    operations = [
        migrations.AlterField(
            model_name="property",
            name="property_type",
            field=models.CharField(
                choices=[
                    ("apartment", "Apartment"),
                    ("studio", "Studio"),
                    ("villa_house", "Villa / House"),
                    ("commercial", "Commercial"),
                    ("land", "Land"),
                    ("office", "Office"),
                    ("retail", "Retail"),
                ],
                db_index=True,
                default="apartment",
                max_length=20,
            ),
        ),
        migrations.RunPython(merge_villa_house, split_villa_house),
    ]
