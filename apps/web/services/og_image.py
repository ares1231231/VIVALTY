"""Dynamic Open Graph card generator for property listings.

Produces a 1200×630 PNG composited from the listing's primary photo with a
dark gradient and the price + location + brand overlaid. This is what shows up
when someone shares a listing on WhatsApp, Facebook, iMessage, etc. — turning
every visitor into a distribution channel.

Design goals:
- **Zero external font dependency.** Pillow 10.1+ bundles a scalable TrueType
  font available via ``ImageFont.load_default(size=...)``, so this works on any
  host (including a clean Linux container) without shipping font files.
- **Never raise to the caller.** If the photo can't be fetched we fall back to a
  branded gradient so the share card always renders.
"""

from __future__ import annotations

import io
import logging
import os
from urllib.parse import urljoin

from django.conf import settings

logger = logging.getLogger("vivalty.og")

WIDTH, HEIGHT = 1200, 630
BRAND = (5, 150, 105)  # emerald-600

# Candidate Unicode-capable TrueType fonts, in preference order, covering the
# three OSes we run on (Railway/Debian → DejaVu/Liberation, Windows → Arial,
# macOS → Arial/Helvetica). These all include € and ² so the price renders
# correctly. We fall back to Pillow's bundled default (Aileron subset) only as
# a last resort, in which case we sanitise glyphs it can't draw.
_REGULAR_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]
_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def _first_existing(paths: list[str]) -> str | None:
    for p in paths:
        if os.path.exists(p):
            return p
    return None


# Resolved once per process.
_REGULAR_PATH = _first_existing(_REGULAR_CANDIDATES)
_BOLD_PATH = _first_existing(_BOLD_CANDIDATES) or _REGULAR_PATH
# True when we have a full Unicode TTF (so € / ² render correctly).
RICH_GLYPHS = _REGULAR_PATH is not None


def _load_font(size: int, *, bold: bool = False):
    from PIL import ImageFont

    path = (_BOLD_PATH if bold else _REGULAR_PATH)
    if path:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            logger.warning("Failed to load TTF %s", path, exc_info=True)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _sanitize(text: str) -> str:
    """Strip glyphs the fallback font can't render, when no rich TTF is present."""
    if RICH_GLYPHS:
        return text
    return (
        text.replace("€", "EUR ")
        .replace("£", "GBP ")
        .replace("²", "2")
        .replace("·", "-")
    )


def _fetch_image_bytes(url: str) -> bytes | None:
    """Fetch the listing photo. Handles remote URLs and local MEDIA files."""
    if not url:
        return None
    try:
        if url.startswith("http://") or url.startswith("https://"):
            import requests

            resp = requests.get(
                url,
                timeout=8,
                headers={"User-Agent": "VivaltyOG/1.0 (+https://vivalty.com)"},
            )
            if resp.ok:
                return resp.content
            return None
        # Local media path (e.g. "/media/properties/2026/01/foo.jpg").
        media_url = settings.MEDIA_URL or "/media/"
        rel = url
        if media_url and url.startswith(media_url):
            rel = url[len(media_url):]
        path = os.path.join(settings.MEDIA_ROOT, rel.lstrip("/"))
        if os.path.exists(path):
            with open(path, "rb") as fh:
                return fh.read()
    except Exception:
        logger.warning("OG image fetch failed for %s", url, exc_info=True)
    return None


def _cover_crop(img, w: int, h: int):
    """Resize + center-crop the image to exactly w×h (object-fit: cover)."""
    from PIL import Image

    src_w, src_h = img.size
    if src_w == 0 or src_h == 0:
        return img.resize((w, h))
    scale = max(w / src_w, h / src_h)
    new_w, new_h = int(src_w * scale) + 1, int(src_h * scale) + 1
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return img.crop((left, top, left + w, top + h))


def _gradient_background():
    """Branded diagonal gradient used when no photo is available."""
    from PIL import Image

    base = Image.new("RGB", (WIDTH, HEIGHT), (10, 12, 16))
    top = Image.new("RGB", (WIDTH, HEIGHT), BRAND)
    mask = Image.new("L", (WIDTH, HEIGHT))
    px = mask.load()
    for y in range(HEIGHT):
        for x in range(0, WIDTH, 4):  # step for speed; mask is low-frequency
            v = int(180 * (1 - (x + y) / (WIDTH + HEIGHT)))
            for dx in range(4):
                if x + dx < WIDTH:
                    px[x + dx, y] = v
    return Image.composite(top, base, mask)


def render_property_og(prop) -> bytes:
    """Return PNG bytes for the share card of ``prop``."""
    from PIL import Image, ImageDraw

    # Base layer — photo or gradient.
    raw = _fetch_image_bytes(getattr(prop, "primary_image_url", None) or "")
    canvas = None
    if raw:
        try:
            photo = Image.open(io.BytesIO(raw)).convert("RGB")
            canvas = _cover_crop(photo, WIDTH, HEIGHT)
        except Exception:
            logger.warning("OG image decode failed for property %s", prop.pk, exc_info=True)
    if canvas is None:
        canvas = _gradient_background()

    # Bottom-up dark scrim for legibility.
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for y in range(HEIGHT):
        # Transparent at top → ~92% black at the very bottom.
        t = max(0.0, (y - HEIGHT * 0.42) / (HEIGHT * 0.58))
        odraw.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, int(235 * (t ** 1.4))))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(canvas)
    margin = 64

    # ── Brand wordmark (top-left) ──
    brand_font = _load_font(40, bold=True)
    badge_w, badge_h = 60, 60
    draw.rounded_rectangle(
        [margin, margin, margin + badge_w, margin + badge_h], radius=14, fill=BRAND
    )
    draw.text((margin + 17, margin + 4), "V", font=_load_font(44, bold=True), fill=(255, 255, 255))
    draw.text((margin + badge_w + 18, margin + 10), "VIVALTY", font=brand_font, fill=(255, 255, 255))

    # ── Location (eyebrow) ──
    city = getattr(getattr(prop, "city", None), "name", "") or ""
    country = getattr(getattr(prop, "country", None), "name", "") or ""
    location = ", ".join([s for s in (city, country) if s])

    loc_font = _load_font(30, bold=True)
    loc_y = HEIGHT - margin - 250
    if location:
        draw.text((margin, loc_y), _sanitize(location.upper()), font=loc_font, fill=(214, 222, 230))

    # ── Title (wrapped, max 2 lines) ──
    title = _sanitize((getattr(prop, "title", "") or "").strip())
    title_font = _load_font(60, bold=True)
    lines = _wrap(draw, title, title_font, WIDTH - 2 * margin, max_lines=2)
    ty = loc_y + 46
    for line in lines:
        draw.text((margin, ty), line, font=title_font, fill=(255, 255, 255))
        ty += 70

    # ── Price (big, bottom-left) ──
    price = _sanitize(_format_price(prop))
    price_font = _load_font(72, bold=True)
    draw.text((margin, HEIGHT - margin - 78), price, font=price_font, fill=(255, 255, 255))

    # ── Specs pill (bottom-right) ──
    specs = _sanitize(_specs_text(prop))
    if specs:
        spec_font = _load_font(30, bold=True)
        bbox = draw.textbbox((0, 0), specs, font=spec_font)
        tw = bbox[2] - bbox[0]
        pill_x1 = WIDTH - margin - tw - 48
        pill_y1 = HEIGHT - margin - 64
        draw.rounded_rectangle(
            [pill_x1, pill_y1, WIDTH - margin, pill_y1 + 56],
            radius=28,
            fill=(255, 255, 255),
        )
        draw.text((pill_x1 + 24, pill_y1 + 12), specs, font=spec_font, fill=(15, 23, 42))

    buf = io.BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _wrap(draw, text: str, font, max_width: int, *, max_lines: int = 2) -> list[str]:
    if not text:
        return []
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
            if len(lines) == max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    # Ellipsize if we ran out of room.
    if len(lines) == max_lines:
        last = lines[-1]
        remaining = " ".join(words)
        if not remaining.endswith(last):
            while last and draw.textbbox((0, 0), last + "…", font=font)[2] > max_width:
                last = last[:-1]
            lines[-1] = (last + "…") if last else last
    return lines


def _format_price(prop) -> str:
    symbols = {"EUR": "€", "GBP": "£", "USD": "$", "CHF": "CHF ", "AED": "AED "}
    currency = (getattr(prop, "currency", "") or "EUR").upper()
    sym = symbols.get(currency, f"{currency} ")
    try:
        n = float(getattr(prop, "price", 0) or 0)
        return f"{sym}{n:,.0f}"
    except (TypeError, ValueError):
        return sym.strip()


def _specs_text(prop) -> str:
    parts = []
    beds = getattr(prop, "bedrooms", None)
    area = getattr(prop, "area_sqm", None)
    ptype = ""
    try:
        ptype = prop.get_property_type_display()
    except Exception:
        ptype = ""
    if beds:
        parts.append(f"{beds} bed")
    if area:
        try:
            parts.append(f"{float(area):.0f} m²")
        except (TypeError, ValueError):
            pass
    if ptype:
        parts.append(ptype)
    return "  ·  ".join(parts)


def absolute_og_url(prop) -> str:
    """Absolute URL of the dynamic OG image for use in <meta> tags."""
    from django.urls import reverse

    path = reverse("web:property_og", kwargs={"pk": prop.pk})
    return urljoin(settings.SITE_URL.rstrip("/") + "/", path.lstrip("/"))
