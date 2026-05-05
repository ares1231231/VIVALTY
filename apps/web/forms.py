"""Django forms used by the server-rendered site.

We keep these tiny on purpose — heavy validation lives in the DRF serializers
so both the API and the website share the same rules.
"""

from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password

from apps.geo.models import City, Country
from apps.properties.models import Lead, Property, PropertyImage
from apps.users.models import Role, User


class EmailLoginForm(AuthenticationForm):
    """Authenticates with email instead of username."""

    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"class": "input", "autofocus": True, "autocomplete": "email"}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "current-password"}),
    )


class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "input", "minlength": 8}),
        min_length=8,
    )

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "role", "company_name")
        widgets = {
            "email": forms.EmailInput(attrs={"class": "input"}),
            "first_name": forms.TextInput(attrs={"class": "input"}),
            "last_name": forms.TextInput(attrs={"class": "input"}),
            "role": forms.Select(attrs={"class": "input"}),
            "company_name": forms.TextInput(attrs={"class": "input"}),
        }

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_password(self) -> str:
        pwd = self.cleaned_data["password"]
        validate_password(pwd)
        return pwd

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class PropertyForm(forms.ModelForm):
    image_urls = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "input", "rows": 3, "placeholder": "https://..."}),
        help_text="One image URL per line.",
    )

    class Meta:
        model = Property
        fields = (
            "title", "description", "property_type", "status",
            "price", "currency", "country", "city", "address",
            "bedrooms", "bathrooms", "area_sqm", "year_built",
            "contact_name", "contact_email", "contact_phone",
        )
        widgets = {
            "title": forms.TextInput(attrs={"class": "input"}),
            "description": forms.Textarea(attrs={"class": "input", "rows": 4}),
            "property_type": forms.Select(attrs={"class": "input"}),
            "status": forms.Select(attrs={"class": "input"}),
            "price": forms.NumberInput(attrs={"class": "input", "step": "0.01"}),
            "currency": forms.Select(
                attrs={"class": "input"},
                choices=[(c, c) for c in ("EUR", "GBP", "CHF", "AED", "USD")],
            ),
            "country": forms.Select(attrs={"class": "input"}),
            "city": forms.Select(attrs={"class": "input"}),
            "address": forms.TextInput(attrs={"class": "input"}),
            "bedrooms": forms.NumberInput(attrs={"class": "input"}),
            "bathrooms": forms.NumberInput(attrs={"class": "input"}),
            "area_sqm": forms.NumberInput(attrs={"class": "input", "step": "0.1"}),
            "year_built": forms.NumberInput(attrs={"class": "input"}),
            "contact_name": forms.TextInput(attrs={"class": "input"}),
            "contact_email": forms.EmailInput(attrs={"class": "input"}),
            "contact_phone": forms.TextInput(attrs={"class": "input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["country"].queryset = Country.objects.all().order_by("name")
        self.fields["city"].queryset = City.objects.select_related("country").all().order_by("country__name", "name")

    def save(self, commit: bool = True, owner: User | None = None) -> Property:
        prop = super().save(commit=False)
        if owner is not None:
            prop.owner = owner
        if commit:
            prop.save()
            self.save_m2m()
            urls = [u.strip() for u in (self.cleaned_data.get("image_urls") or "").splitlines() if u.strip()]
            for i, url in enumerate(urls):
                PropertyImage.objects.create(property=prop, url=url, position=i)
        return prop


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ("name", "email", "phone", "message")
        widgets = {
            "name": forms.TextInput(attrs={"class": "input"}),
            "email": forms.EmailInput(attrs={"class": "input"}),
            "phone": forms.TextInput(attrs={"class": "input"}),
            "message": forms.Textarea(attrs={"class": "input", "rows": 3}),
        }
