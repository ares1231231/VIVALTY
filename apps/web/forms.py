"""Django forms used by the server-rendered site.

We keep these tiny on purpose — heavy validation lives in the DRF serializers
so both the API and the website share the same rules.
"""

from __future__ import annotations

from decimal import Decimal

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password

from apps.geo.models import City, Country
from apps.properties.models import Lead, Property, PropertyImage, PropertyType
from apps.users.models import Role, User
from apps.web.models import InvestorInquiry, InvestorProfile


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


class InvestorInquiryForm(forms.ModelForm):
    """Investor-relations capture form used by the hero, methodology page,
    premium analytics paywall and footer.
    """

    class Meta:
        model = InvestorInquiry
        fields = (
            "name",
            "email",
            "phone",
            "profile",
            "budget_max",
            "budget_currency",
            "markets_of_interest",
            "message",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": "input", "placeholder": "Full name"}),
            "email": forms.EmailInput(attrs={"class": "input", "placeholder": "you@example.com"}),
            "phone": forms.TextInput(attrs={"class": "input", "placeholder": "+1 555 0100"}),
            "profile": forms.Select(attrs={"class": "input"}),
            "budget_max": forms.NumberInput(
                attrs={"class": "input", "step": "1000", "placeholder": "e.g. 750 000"}
            ),
            "budget_currency": forms.Select(
                attrs={"class": "input"},
                choices=[(c, c) for c in ("EUR", "GBP", "CHF", "AED", "USD")],
            ),
            "markets_of_interest": forms.TextInput(
                attrs={"class": "input", "placeholder": "Lisbon, Dubai, Manchester…"}
            ),
            "message": forms.Textarea(
                attrs={
                    "class": "input",
                    "rows": 3,
                    "placeholder": "Tell us about your investment goals (yield, hold horizon, capital available)…",
                }
            ),
        }


# ─── Listing wizard forms ───────────────────────────────────────────────────
#
# One small Form per wizard step. They never `.save()` directly — the wizard
# service is the single owner of persistence. Each form is responsible for
# validation + coercion + producing a dict that gets merged into the session
# draft (see `apps/web/services/listing_wizard.py`).


class _WizardForm(forms.Form):
    """Base class: every wizard form returns a dict that the service merges
    into `request.session['listing_draft']`."""

    def to_draft(self) -> dict:
        return {k: v for k, v in self.cleaned_data.items() if v not in (None, "")}


class ListingTypeForm(_WizardForm):
    """Step 1 — what is being listed."""

    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "e.g. Sun-drenched 2-bed pied-à-terre, Le Marais",
            "autocomplete": "off",
        }),
        help_text="Investors skim — lead with the headline that makes them click.",
    )
    property_type = forms.ChoiceField(
        choices=PropertyType.choices,
        widget=forms.RadioSelect(attrs={"class": "vv-listing-type-input"}),
    )


class ListingLocationForm(_WizardForm):
    """Step 2 — where it is."""

    country = forms.ModelChoiceField(
        queryset=Country.objects.order_by("name"),
        widget=forms.Select(attrs={"class": "input", "id": "id_country"}),
    )
    city = forms.ModelChoiceField(
        queryset=City.objects.select_related("country").order_by("name"),
        widget=forms.Select(attrs={"class": "input", "id": "id_city"}),
    )
    address = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "Start typing an address…",
            "autocomplete": "off",
            "id": "id_address",
        }),
    )
    latitude = forms.DecimalField(
        required=False,
        max_digits=9,
        decimal_places=6,
        widget=forms.HiddenInput(attrs={"id": "id_latitude"}),
    )
    longitude = forms.DecimalField(
        required=False,
        max_digits=9,
        decimal_places=6,
        widget=forms.HiddenInput(attrs={"id": "id_longitude"}),
    )

    def clean(self):
        cleaned = super().clean()
        country = cleaned.get("country")
        city = cleaned.get("city")
        if country and city and city.country_id != country.id:
            self.add_error("city", "Selected city is not in the selected country.")
        return cleaned

    def to_draft(self) -> dict:
        data = self.cleaned_data
        return {
            "country_id": data["country"].id,
            "country_code": data["country"].code,
            "country_name": data["country"].name,
            "city_id": data["city"].id,
            "city_name": data["city"].name,
            "address": data.get("address") or "",
            "latitude": str(data["latitude"]) if data.get("latitude") else "",
            "longitude": str(data["longitude"]) if data.get("longitude") else "",
        }


class ListingSpecsForm(_WizardForm):
    """Step 3 — bedrooms / bathrooms / area / description."""

    bedrooms = forms.IntegerField(
        required=False, min_value=0, max_value=50,
        widget=forms.NumberInput(attrs={"class": "input", "placeholder": "2"}),
    )
    bathrooms = forms.IntegerField(
        required=False, min_value=0, max_value=20,
        widget=forms.NumberInput(attrs={"class": "input", "placeholder": "1"}),
    )
    area_sqm = forms.DecimalField(
        max_digits=8, decimal_places=2, min_value=Decimal("1"),
        widget=forms.NumberInput(attrs={"class": "input", "step": "0.1", "placeholder": "85"}),
    )
    year_built = forms.IntegerField(
        required=False, min_value=1500, max_value=2100,
        widget=forms.NumberInput(attrs={"class": "input", "placeholder": "1890"}),
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "input",
            "rows": 6,
            "id": "id_description",
            "placeholder": (
                "Tell the investor story: location & lifestyle, what makes this "
                "property distinctive, why now."
            ),
        }),
    )

    def to_draft(self) -> dict:
        data = self.cleaned_data
        return {
            "bedrooms": data.get("bedrooms"),
            "bathrooms": data.get("bathrooms"),
            "area_sqm": str(data["area_sqm"]) if data.get("area_sqm") else "",
            "year_built": data.get("year_built"),
            "description": data.get("description") or "",
        }


class ListingPriceForm(_WizardForm):
    """Step 5 — price, currency, contact, agency."""

    price = forms.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("1"),
        widget=forms.NumberInput(attrs={
            "class": "input", "step": "1000", "placeholder": "750000",
            "id": "id_price",
        }),
    )
    currency = forms.ChoiceField(
        choices=[(c, c) for c in ("EUR", "GBP", "CHF", "AED", "USD")],
        initial="EUR",
        widget=forms.Select(attrs={"class": "input", "id": "id_currency"}),
    )
    contact_name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "Sophie Laurent"}),
    )
    contact_email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "input", "placeholder": "sophie@agency.com"}),
    )
    contact_phone = forms.CharField(
        required=False, max_length=32,
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "+33 1 23 45 67 89"}),
    )
    listing_agency = forms.CharField(
        required=False, max_length=200,
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "e.g. Hamptons International"}),
    )
    listing_ref = forms.CharField(
        required=False, max_length=64,
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "MLS-12345"}),
    )

    def to_draft(self) -> dict:
        data = self.cleaned_data
        return {
            "price": str(data["price"]),
            "currency": data["currency"],
            "contact_name": data["contact_name"],
            "contact_email": data["contact_email"],
            "contact_phone": data.get("contact_phone") or "",
            "listing_agency": data.get("listing_agency") or "",
            "listing_ref": data.get("listing_ref") or "",
        }


# ─── Owner upgrade (investor → owner intercept) ─────────────────────────────


class BecomeOwnerForm(forms.Form):
    """Single-screen role upgrade for authenticated investors who hit the
    listing flow. We collect contact details + an authorization checkbox
    and flip ``user.role = Role.OWNER`` on submit.
    """

    company_name = forms.CharField(
        required=False, max_length=200,
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "If listing as an agency or developer (optional)",
        }),
    )
    phone = forms.CharField(
        max_length=32,
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "+44 20 7946 0000",
        }),
    )
    confirm_authorized = forms.BooleanField(
        required=True,
        label="I am authorized to list this property on Vivalty.",
        error_messages={"required": "Please confirm you're authorized to list this property."},
    )

    def apply(self, user: User) -> User:
        user.role = Role.OWNER
        user.company_name = self.cleaned_data.get("company_name") or user.company_name
        user.phone = self.cleaned_data.get("phone") or user.phone
        user.save(update_fields=["role", "company_name", "phone"])
        return user


# ─── Edit form (published listings) ─────────────────────────────────────────


class PropertyEditForm(forms.ModelForm):
    """In-place edit on a single page — re-using the single-page form used by
    legacy `/owner/new/`. The wizard is only for *new* listings; editing
    an existing one shouldn't make owners click through 5 steps.
    """

    class Meta:
        model = Property
        fields = (
            "title", "description", "property_type", "status",
            "price", "currency", "country", "city", "address",
            "latitude", "longitude",
            "bedrooms", "bathrooms", "area_sqm", "year_built",
            "contact_name", "contact_email", "contact_phone",
            "listing_agency", "listing_ref",
        )
        widgets = {
            "title": forms.TextInput(attrs={"class": "input"}),
            "description": forms.Textarea(attrs={"class": "input", "rows": 5}),
            "property_type": forms.Select(attrs={"class": "input"}),
            "status": forms.Select(attrs={"class": "input"}),
            "price": forms.NumberInput(attrs={"class": "input", "step": "1000"}),
            "currency": forms.Select(
                attrs={"class": "input"},
                choices=[(c, c) for c in ("EUR", "GBP", "CHF", "AED", "USD")],
            ),
            "country": forms.Select(attrs={"class": "input"}),
            "city": forms.Select(attrs={"class": "input"}),
            "address": forms.TextInput(attrs={"class": "input"}),
            "latitude": forms.NumberInput(attrs={"class": "input", "step": "0.000001"}),
            "longitude": forms.NumberInput(attrs={"class": "input", "step": "0.000001"}),
            "bedrooms": forms.NumberInput(attrs={"class": "input"}),
            "bathrooms": forms.NumberInput(attrs={"class": "input"}),
            "area_sqm": forms.NumberInput(attrs={"class": "input", "step": "0.1"}),
            "year_built": forms.NumberInput(attrs={"class": "input"}),
            "contact_name": forms.TextInput(attrs={"class": "input"}),
            "contact_email": forms.EmailInput(attrs={"class": "input"}),
            "contact_phone": forms.TextInput(attrs={"class": "input"}),
            "listing_agency": forms.TextInput(attrs={"class": "input"}),
            "listing_ref": forms.TextInput(attrs={"class": "input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["country"].queryset = Country.objects.order_by("name")
        self.fields["city"].queryset = (
            City.objects.select_related("country").order_by("country__name", "name")
        )


__all__ = [
    "EmailLoginForm",
    "RegisterForm",
    "PropertyForm",
    "PropertyEditForm",
    "LeadForm",
    "InvestorInquiryForm",
    "InvestorProfile",
    "ListingTypeForm",
    "ListingLocationForm",
    "ListingSpecsForm",
    "ListingPriceForm",
    "BecomeOwnerForm",
]
