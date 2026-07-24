"""List-your-property wizard service.

A small state-machine + persistence layer that:
- Keeps wizard answers in the user's session (single source of truth)
- Stashes uploaded images under a per-session UUID prefix (local disk or R2/S3)
- Knows which step is next based on what has been filled
- Renders a *live* score preview by calling the existing scoring service
  with the in-flight values (no Property row is created until publish)
- On publish, atomically creates the Property + PropertyImage rows, moves
  the stashed files into the canonical `properties/<yyyy>/<mm>/` folder,
  marks the listing PENDING for owners / ACTIVE for staff so the editorial
  desk can curate before public visibility.

Why session-only (no DB drafts in v1):
- The `Property` model's `price` / `country` / `city` are non-nullable, so
  scattering placeholders across the catalogue to support drafts pollutes
  every read query (best-match ordering, country avg score, etc.).
- The wizard is short (≈5 steps, ≈3 minutes) — Airbnb's first-time-listing
  flow is also session-state until the final commit.
"""

from __future__ import annotations

import os
import shutil
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.files.storage import FileSystemStorage, default_storage
from django.db import transaction
from django.http import HttpRequest
from django.utils.text import slugify

from apps.geo.models import City, Country
from apps.properties.models import Property, PropertyImage, PropertyType, Status
from apps.properties.services.scoring import compute_score
from apps.users.models import Role

SESSION_KEY = "listing_draft"

# Ordered step list — the URLs / progress bar both key off this.
STEPS: tuple[str, ...] = ("type", "location", "specs", "photos", "price")

# Every key the templates may read. We seed the draft dict with all of
# them on first access so `{{ draft.foo|default:"" }}` and similar
# filter chains never trip Django's strict template-lookup behaviour.
_DRAFT_DEFAULTS: dict[str, object] = {
    # Step 1
    "title": "",
    "property_type": "",
    "property_type_display": "",
    # Step 2
    "country_id": None,
    "country_code": "",
    "country_name": "",
    "city_id": None,
    "city_name": "",
    "address": "",
    "latitude": "",
    "longitude": "",
    # Step 3
    "bedrooms": None,
    "bathrooms": None,
    "area_sqm": "",
    "year_built": None,
    "description": "",
    # Step 4
    "images": [],
    "stash_id": "",
    # Step 5
    "price": "",
    "currency": "",
    "contact_name": "",
    "contact_email": "",
    "contact_phone": "",
    "listing_agency": "",
    "listing_ref": "",
}

STEP_LABELS = {
    "type": "Property type",
    "location": "Location",
    "specs": "Details",
    "photos": "Photos",
    "price": "Price & contact",
}

REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "type": ("property_type", "title"),
    "location": ("country_id", "city_id"),
    "specs": ("area_sqm",),
    "photos": (),  # optional but encouraged
    "price": ("price", "contact_name", "contact_email"),
}

CURRENCY_BY_COUNTRY = {
    "FR": "EUR", "ES": "EUR", "IT": "EUR", "PT": "EUR",
    "GB": "GBP", "CH": "CHF", "AE": "AED",
}


# ─── Dataclass-friendly accessors ────────────────────────────────────────────

@dataclass
class ScorePreview:
    score: int
    yield_pct: float
    roi_min: float
    roi_max: float
    is_estimated: bool
    breakdown: dict[str, Any]
    confidence: str  # "verified" | "estimated" | "baseline"
    confidence_label: str


# ─── Session helpers ─────────────────────────────────────────────────────────

def get_draft(request: HttpRequest) -> dict:
    """Return the in-flight wizard draft, lazily seeded with every key
    Django templates may need to read so default-filter chains never
    raise ``VariableDoesNotExist``.
    """
    draft = request.session.get(SESSION_KEY)
    if draft is None:
        draft = dict(_DRAFT_DEFAULTS)
        draft["images"] = []  # avoid sharing the same list across sessions
        request.session[SESSION_KEY] = draft
        request.session.modified = True
    else:
        # Backfill any missing keys (sessions that pre-date this rev).
        missing = {k: v for k, v in _DRAFT_DEFAULTS.items() if k not in draft}
        if missing:
            draft.update(missing)
            if "images" not in draft or draft["images"] is None:
                draft["images"] = []
            request.session[SESSION_KEY] = draft
            request.session.modified = True
    return draft


def update_draft(request: HttpRequest, data: dict) -> dict:
    draft = get_draft(request)
    draft.update(data)
    request.session[SESSION_KEY] = draft
    request.session.modified = True
    return draft


def clear_draft(request: HttpRequest) -> None:
    draft = request.session.get(SESSION_KEY) or {}
    _wipe_stash(draft.get("stash_id"))
    request.session.pop(SESSION_KEY, None)
    request.session.modified = True


def _ensure_stash(request: HttpRequest) -> str:
    """Return (and lazily create) the per-session UUID stash folder for
    uploaded images, persisted on disk and tracked in the session draft.
    """
    draft = get_draft(request)
    stash_id = draft.get("stash_id")
    if not stash_id:
        stash_id = uuid.uuid4().hex
        update_draft(request, {"stash_id": stash_id})
    if _uses_local_media():
        Path(_stash_path(stash_id)).mkdir(parents=True, exist_ok=True)
    return stash_id


def _uses_local_media() -> bool:
    return isinstance(default_storage, FileSystemStorage)


def _stash_path(stash_id: str) -> str:
    """Filesystem path for local dev only (object storage uses default_storage)."""
    return os.path.join(settings.MEDIA_ROOT, "listing_drafts", stash_id)


def _wipe_stash(stash_id: str | None) -> None:
    if not stash_id:
        return
    prefix = f"listing_drafts/{stash_id}"
    try:
        _, files = default_storage.listdir(prefix)
        for name in files:
            default_storage.delete(f"{prefix}/{name}")
    except (FileNotFoundError, NotImplementedError, OSError):
        pass
    if _uses_local_media():
        path = Path(_stash_path(stash_id))
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)


# ─── Step navigation ─────────────────────────────────────────────────────────

def is_step_complete(draft: dict, step: str) -> bool:
    fields = REQUIRED_FIELDS.get(step, ())
    return all(draft.get(f) not in (None, "") for f in fields)


def progress(draft: dict, current: str) -> list[dict]:
    """Return one row per step for the progress bar."""
    rows: list[dict] = []
    current_idx = STEPS.index(current) if current in STEPS else -1
    for i, step in enumerate(STEPS):
        state = "future"
        if i < current_idx:
            state = "complete" if is_step_complete(draft, step) else "incomplete"
        elif i == current_idx:
            state = "active"
        rows.append({
            "key": step,
            "label": STEP_LABELS[step],
            "index": i + 1,
            "state": state,
            "complete": state == "complete",
            "active": state == "active",
        })
    return rows


def next_step(current: str) -> str | None:
    try:
        i = STEPS.index(current)
    except ValueError:
        return None
    return STEPS[i + 1] if i + 1 < len(STEPS) else None


def prev_step(current: str) -> str | None:
    try:
        i = STEPS.index(current)
    except ValueError:
        return None
    return STEPS[i - 1] if i - 1 >= 0 else None


def can_review(draft: dict) -> bool:
    """Every required step must be filled before we render /list/review/."""
    return all(is_step_complete(draft, s) for s in STEPS if REQUIRED_FIELDS[s])


# ─── Image stash ─────────────────────────────────────────────────────────────

def add_image(request: HttpRequest, uploaded_file) -> dict:
    """Persist an uploaded file under the session stash and append it to the
    draft images list. Returns the stash record (path, filename, position).
    """
    stash_id = _ensure_stash(request)
    safe_name = _safe_filename(uploaded_file.name)
    rel_path = os.path.join("listing_drafts", stash_id, safe_name)
    saved = default_storage.save(rel_path, uploaded_file)
    draft = get_draft(request)
    images: list[dict] = draft.setdefault("images", [])
    record = {
        "id": uuid.uuid4().hex,
        "kind": "upload",
        "path": saved,                            # MEDIA-relative
        "url": default_storage.url(saved),        # served at /media/...
        "filename": safe_name,
        "position": len(images),
    }
    images.append(record)
    update_draft(request, {"images": images})
    return record


def add_image_url(request: HttpRequest, raw_url: str) -> dict:
    """Append an externally-hosted image (paste-URL fallback)."""
    draft = get_draft(request)
    images: list[dict] = draft.setdefault("images", [])
    record = {
        "id": uuid.uuid4().hex,
        "kind": "url",
        "path": "",
        "url": raw_url,
        "filename": raw_url.rsplit("/", 1)[-1][:80],
        "position": len(images),
    }
    images.append(record)
    update_draft(request, {"images": images})
    return record


def remove_image(request: HttpRequest, image_id: str) -> None:
    draft = get_draft(request)
    images: list[dict] = draft.get("images", [])
    keep: list[dict] = []
    for img in images:
        if img["id"] == image_id:
            if img.get("kind") == "upload" and img.get("path"):
                default_storage.delete(img["path"])
            continue
        keep.append(img)
    for i, img in enumerate(keep):
        img["position"] = i
    update_draft(request, {"images": keep})


def reorder_images(request: HttpRequest, ordered_ids: list[str]) -> None:
    draft = get_draft(request)
    by_id = {img["id"]: img for img in draft.get("images", [])}
    new_list: list[dict] = []
    for i, image_id in enumerate(ordered_ids):
        img = by_id.get(image_id)
        if img is None:
            continue
        img["position"] = i
        new_list.append(img)
    update_draft(request, {"images": new_list})


def _safe_filename(name: str) -> str:
    base, _, ext = name.rpartition(".")
    base = slugify(base) or "image"
    ext = (ext or "jpg").lower()[:5]
    return f"{base}-{uuid.uuid4().hex[:8]}.{ext}"


# ─── Live score preview ──────────────────────────────────────────────────────

def score_preview(draft: dict) -> ScorePreview | None:
    """Compute a *preview* of the AI score from in-flight wizard values.

    Returns ``None`` while not enough fields are filled. Otherwise we call
    the canonical scoring service so the wizard preview matches what gets
    persisted on publish — guarantees zero drift.
    """
    country_id = draft.get("country_id")
    if not country_id:
        return None
    try:
        country = Country.objects.get(pk=country_id)
    except Country.DoesNotExist:
        return None

    city = None
    if (city_id := draft.get("city_id")):
        try:
            city = City.objects.get(pk=city_id, country=country)
        except City.DoesNotExist:
            city = None

    price = _to_decimal(draft.get("price"))
    if price is None or price <= 0:
        return None

    area = _to_decimal(draft.get("area_sqm"))

    result = compute_score(
        city=city,
        country=country,
        price=price,
        area_sqm=area,
        is_featured=False,
    )

    if city and (city.avg_rental_yield and city.investment_score):
        confidence = "verified" if not result.is_estimated else "estimated"
    else:
        confidence = "baseline"
    label_map = {
        "verified": "City-level data confirmed",
        "estimated": "Estimated from market baselines",
        "baseline": "Country baseline (refine for higher confidence)",
    }
    return ScorePreview(
        score=result.investment_score,
        yield_pct=float(result.rental_yield),
        roi_min=float(result.estimated_roi_min),
        roi_max=float(result.estimated_roi_max),
        is_estimated=result.is_estimated,
        breakdown=result.breakdown,
        confidence=confidence,
        confidence_label=label_map[confidence],
    )


# ─── Publish ─────────────────────────────────────────────────────────────────

@transaction.atomic
def publish_draft(request: HttpRequest) -> Property:
    """Create the Property + PropertyImage rows from the session draft.

    Owners' submissions land in `Status.PENDING` so the Vivalty editorial
    desk can review before they go public; staff / admins publish straight
    to `Status.ACTIVE`. The InvestmentMetric is computed automatically by
    the post_save signal on Property.
    """
    from apps.billing.services.quotas import can_create_listing

    user = request.user
    draft = get_draft(request)

    if not can_review(draft):
        raise ValueError("Draft is incomplete.")

    allowed, quota_msg = can_create_listing(user)
    if not allowed:
        raise ValueError(quota_msg)

    country = Country.objects.get(pk=draft["country_id"])
    city = City.objects.get(pk=draft["city_id"])

    auto_active = user.is_staff or getattr(user, "role", None) == Role.ADMIN
    status = Status.ACTIVE if auto_active else Status.PENDING

    prop = Property.objects.create(
        owner=user,
        title=(draft.get("title") or "")[:200],
        description=draft.get("description") or "",
        property_type=draft.get("property_type") or PropertyType.APARTMENT,
        status=status,
        price=_to_decimal(draft.get("price")) or Decimal("0"),
        currency=draft.get("currency") or "EUR",
        country=country,
        city=city,
        address=draft.get("address") or "",
        latitude=_to_decimal(draft.get("latitude")),
        longitude=_to_decimal(draft.get("longitude")),
        bedrooms=_to_int(draft.get("bedrooms")),
        bathrooms=_to_int(draft.get("bathrooms")),
        area_sqm=_to_decimal(draft.get("area_sqm")),
        year_built=_to_int(draft.get("year_built")),
        contact_name=(draft.get("contact_name") or user.get_full_name() or "")[:120],
        contact_email=draft.get("contact_email") or user.email,
        contact_phone=draft.get("contact_phone") or "",
        listing_agency=draft.get("listing_agency") or "",
        listing_ref=draft.get("listing_ref") or "",
    )

    # Persist images: moves files out of the stash into the canonical
    # `properties/<yyyy>/<mm>/` folder under MEDIA_ROOT.
    images = sorted(draft.get("images", []), key=lambda i: i.get("position", 0))
    for i, img in enumerate(images):
        if img.get("kind") == "upload" and img.get("path"):
            pi = PropertyImage(property=prop, position=i, caption=img.get("filename", ""))
            # Reopen via default_storage; assigning to the ImageField re-saves
            # under upload_to="properties/%Y/%m/" and updates the path.
            with default_storage.open(img["path"], "rb") as fh:
                pi.image.save(img["filename"], fh, save=False)
            pi.save()
            default_storage.delete(img["path"])
        elif img.get("url"):
            PropertyImage.objects.create(
                property=prop,
                url=img["url"],
                position=i,
            )

    _wipe_stash(draft.get("stash_id"))
    clear_draft(request)
    return prop


# ─── Coercion helpers ────────────────────────────────────────────────────────

def _to_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _to_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "STEPS",
    "STEP_LABELS",
    "ScorePreview",
    "get_draft",
    "update_draft",
    "clear_draft",
    "is_step_complete",
    "progress",
    "next_step",
    "prev_step",
    "can_review",
    "add_image",
    "add_image_url",
    "remove_image",
    "reorder_images",
    "score_preview",
    "publish_draft",
    "CURRENCY_BY_COUNTRY",
]
