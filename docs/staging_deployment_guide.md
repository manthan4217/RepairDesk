# RepairDesk – Staging Deployment Guide (Railway / Containerized PaaS)

This operational guide details the configuration, deployment process, storage considerations, and verification procedures for deploying RepairDesk to a containerized staging environment (such as Railway or equivalent PaaS platforms).

---

## 1. Environment Variables Specification

All configuration in staging and production must be injected via environment variables. Never commit secrets, credentials, or environment files into the Git repository.

| Variable | Required | Recommended Staging Value | Description |
| :--- | :---: | :--- | :--- |
| `DJANGO_SETTINGS_MODULE` | **Yes** | `config.settings.production` | Selects production settings with strict security and MySQL guards. |
| `SECRET_KEY` | **Yes** | *(Cryptographically random string)* | High-entropy random key (minimum 50 characters). Generate via `django.core.management.utils.get_random_secret_key()`. |
| `DEBUG` | **Yes** | `False` | Disables debug mode and Django detailed error pages. |
| `ALLOWED_HOSTS` | **Yes** | `staging.repairdesk.example.com,repairdesk-staging.up.railway.app` | Comma-separated list of fully qualified hostnames allowed to serve requests. **Never use wildcards (`*`)**. |
| `CSRF_TRUSTED_ORIGINS` | **Yes** | `https://staging.repairdesk.example.com,https://repairdesk-staging.up.railway.app` | Comma-separated list of trusted origins with scheme (`https://`). Required by Django 5.2 for POST/CSRF validation over HTTPS. |
| `DATABASE_URL` | **Yes** | `mysql://${MYSQLUSER}:${MYSQLPASSWORD}@${MYSQLHOST}:${MYSQLPORT}/${MYSQLDATABASE}` | MySQL connection URL. Parsed automatically by `django-environ`. Overrides individual `DB_*` variables. |
| `CONN_MAX_AGE` | No | `60` | Persistent connection age in seconds (defaults to 60). |
| `CONN_HEALTH_CHECKS` | No | `True` | Validates database connection health prior to reuse (defaults to `True`). |
| `WEB_CONCURRENCY` | No | `3` | Number of Gunicorn worker processes (defaults to `3` or `2 * cores + 1`). |

> [!IMPORTANT]
> The production configuration (`config.settings.production`) enforces an explicit assertion requiring `django.db.backends.mysql`. If `DATABASE_URL` resolves to SQLite or any non-MySQL backend, Django startup will immediately abort with `ImproperlyConfigured`.

---

## 2. Build and Start Commands

### Build Command
On Railway or container PaaS platforms, configure the build phase command to invoke `build.sh`:
```bash
bash build.sh
```
`build.sh` performs the following operations:
1. Enables immediate failure on error (`set -o errexit`).
2. Installs pinned dependencies from `requirements.txt`.
3. Runs `python manage.py collectstatic --noinput` to compile static assets and generate WhiteNoise manifests.

### Start Command (Procfile)
The application process is defined in the root `Procfile`:
```
web: gunicorn config.wsgi:application
```
For production tuning, Gunicorn can be launched with explicit worker concurrency and timeout limits:
```bash
gunicorn config.wsgi:application --workers 3 --threads 2 --timeout 60 --access-logfile - --error-logfile -
```
* **Workers**: Standard recommendation is `(2 * CPU cores) + 1`. For standard 1-vCPU staging containers, 3 workers provide optimal concurrency.
* **Threads**: 2 threads per worker allow handling brief I/O delays during MySQL or asset operations.
* **Timeout**: 60 seconds prevents stalled worker processes from holding resources.
* **Logging**: Outputting to stdout/stderr (`-`) ensures compatibility with container log collectors.

---

## 3. Database Migration Strategy

### Why Migrations Are Excluded from `build.sh`
Migrations are intentionally **excluded** from `build.sh` for the following critical operational reasons:
1. **Build Phase Isolation**: During the build phase, production database connections may not be reachable or network-isolated.
2. **Failed Build Protection**: Running migrations during the build phase risks applying schema changes even if subsequent build steps fail, leaving the database in an inconsistent state ahead of deployment.
3. **Concurrency Hazards**: Multi-instance deployments trigger multiple parallel builds. Running migrations during the build phase could cause concurrent execution of migration locks.

### Post-Deploy Migration Command
Run migrations as a one-off post-deploy release command or via an isolated container task:
```bash
python manage.py migrate --noinput
```

### Zero-Downtime Migration Principles
When deploying schema updates:
1. **Additive Changes First**: Add new nullable columns or new tables before deploying application code that references them.
2. **Backfill Data**: Populate required column values asynchronously or via controlled data migrations.
3. **Contract Constraints**: Apply non-null constraints and drop legacy fields in subsequent releases once code no longer references old schemas.

---

## 4. Static and Media Asset Handling

### Static Files (WhiteNoise)
Static files are handled directly by the application container using WhiteNoise:
- `whitenoise.middleware.WhiteNoiseMiddleware` is positioned immediately following `django.middleware.security.SecurityMiddleware`.
- `STORAGES["staticfiles"]["BACKEND"]` uses `whitenoise.storage.CompressedManifestStaticFilesStorage`.
- Static files receive unique content-hashed filenames (e.g. `site.a1b2c3d4e5f6.css`), enabling aggressive long-term HTTP caching (`Cache-Control: max-age=31536000, immutable`).
- Gzip and Brotli compressed versions are pre-generated during `collectstatic`.
- External assets (Bootstrap 5.3 and Chart.js) are loaded from jsDelivr CDN, keeping the local static footprint minimal.

### Media Files (Uploaded Attachments)
Containerized PaaS filesystems (including Railway) are **ephemeral** by default:
- Any file written to the local disk inside the container (e.g. customer attachments under `media/`) will be lost when the container restarts, scales, or redeploys.
- **Staging Considerations**: In staging environments, user attachments may be stored locally for ephemeral smoke testing, but will not survive deployments unless a persistent volume is mounted to the `media/` path.
- **Production Architecture**: For durable production deployments, configure cloud object storage (e.g. AWS S3, Google Cloud Storage, or Cloudflare R2) via `django-storages` or attach a persistent volume to the container's `MEDIA_ROOT`.

---

## 5. Deployment Verification Checklist

Execute these checks after initiating staging deployment:

### Pre-Deployment Checks
- [ ] Database credentials verified and MySQL service running.
- [ ] `SECRET_KEY` generated and configured in environment.
- [ ] `ALLOWED_HOSTS` matches exact assigned staging domains.
- [ ] `CSRF_TRUSTED_ORIGINS` includes exact `https://` staging domains.
- [ ] `DATABASE_URL` accurately points to MySQL staging instance.
- [ ] All local tests passing (`142/142` baseline + configuration test suite).

### Post-Deployment Health Check & Smoke Test
1. **HTTP to HTTPS Redirection**:
   ```bash
   curl -I http://staging.repairdesk.example.com
   # Expected: 301 Moved Permanently to https://...
   ```
2. **Root Endpoint**:
   ```bash
   curl -I https://staging.repairdesk.example.com/
   # Expected: 302 Found (Redirects to /accounts/login/?next=/)
   ```
3. **Login Page**:
   ```bash
   curl -I https://staging.repairdesk.example.com/accounts/login/
   # Expected: 200 OK
   ```
4. **Static Asset Verification (WhiteNoise)**:
   ```bash
   curl -I https://staging.repairdesk.example.com/static/css/site.css
   # Expected: 200 OK, Content-Type: text/css, Cache-Control header present
   ```
5. **Security Headers Verification**:
   Verify response headers on HTTPS requests:
   - `X-Content-Type-Options: nosniff`
   - `X-Frame-Options: DENY`
   - `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
6. **Application Workflow**:
   - Log in using a pre-seeded technician account.
   - Access Dashboard (`/dashboard/`).
   - Create a service ticket and assign a technician.
   - Verify ticket state transition to In Progress and Completed.
