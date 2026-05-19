# Production deployment (Railway + Cloudflare)

## Custom domain and `www`

1. In **Railway** → VIVALTY service → **Settings** → **Networking** → add `vivalty.com` and `www.vivalty.com`.
2. At your DNS registrar (or Cloudflare):

| Type  | Name | Value |
|-------|------|--------|
| CNAME | `@`  | Railway target for apex (or use Cloudflare CNAME flattening) |
| CNAME | `www` | Same Railway hostname as apex (e.g. `vivalty-production.up.railway.app`) |

3. The app redirects `www.vivalty.com` → `https://vivalty.com` via `CanonicalHostMiddleware` once `www` resolves.

Set in Railway variables:

```
CANONICAL_HOST=vivalty.com
SITE_URL=https://vivalty.com
```

---

## Property photos (Cloudflare R2)

Railway’s filesystem is ephemeral. Enable object storage so listing uploads survive redeploys.

### 1. Create an R2 bucket

1. Cloudflare dashboard → **R2** → **Create bucket** (e.g. `vivalty-media`).
2. **Settings** → enable **Public access** *or* attach a custom domain (recommended: `media.vivalty.com`).
3. **Manage R2 API tokens** → Create token with **Object Read & Write** on that bucket.

### 2. Railway variables

```env
AWS_ACCESS_KEY_ID=<R2 access key id>
AWS_SECRET_ACCESS_KEY=<R2 secret access key>
AWS_STORAGE_BUCKET_NAME=vivalty-media
AWS_S3_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
AWS_S3_REGION_NAME=auto
AWS_S3_CUSTOM_DOMAIN=media.vivalty.com
```

If using the default `*.r2.dev` public URL instead of a custom domain, set `AWS_S3_CUSTOM_DOMAIN` to that host (no `https://` prefix).

### 3. Redeploy

After variables are saved, redeploy. New uploads go to R2; `PropertyImage.image.url` serves from your public domain.

Existing files on the old local disk are **not** migrated automatically—re-upload or copy objects into the bucket under `properties/` and `listing_drafts/` prefixes if needed.

---

## SEO

These routes are built in:

- `https://vivalty.com/robots.txt`
- `https://vivalty.com/sitemap.xml`

`robots.txt` uses `SITE_URL` for the sitemap line. Submit the sitemap in [Google Search Console](https://search.google.com/search-console).

---

## Verify after deploy

```powershell
.\scripts\verify-production.ps1 -BaseUrl https://vivalty.com
```

Check `robots.txt`, `sitemap.xml`, and upload a test photo on `/list/`.
