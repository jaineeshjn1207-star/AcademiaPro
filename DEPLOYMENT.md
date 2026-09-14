# AcademiaPro — Production Deployment & DevOps Architecture Guide

This document provides complete, step-by-step instructions for deploying AcademiaPro to production environments.

---

## 1. System Architecture Overview

AcademiaPro follows a decoupled, cloud-ready architecture:

```text
                                  +---------------------------------------+
                                  |         DNS & CDN / SSL (Cloudflare)   |
                                  +---------------------------------------+
                                            |                    |
                         Frontend Traffic   |                    | API & Media
                                            v                    v
                  +--------------------------------+   +-----------------------------------+
                  |      React 18 SPA (Vercel/     |   |      Django REST API (Gunicorn/   |
                  |     Cloudflare Pages/Nginx)    |   |     Render/Ubuntu VPS/AWS ECS)    |
                  +--------------------------------+   +-----------------------------------+
                                   |                                     |
                                   | AJAX (JWT Auth)                     |
                                   +------------------------------------>|
                                                                         v
                                                       +-----------------------------------+
                                                       |      PostgreSQL Database          |
                                                       |   (Neon / AWS RDS / Supabase)     |
                                                       +-----------------------------------+
                                                                         |
                                                       +-----------------------------------+
                                                       |   Google Gemini AI & Run Runtimes |
                                                       |     (Python, Node, C++, Java)     |
                                                       +-----------------------------------+
```

---

## 2. Environment Variables Reference

### Backend (`backend/.env` or Cloud Platform Environment)

| Variable | Required | Default / Example | Purpose |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | **Yes** | `d4f8a...` | Cryptographic secret for signing sessions, JWTs, and tokens. |
| `DJANGO_DEBUG` | **Yes** | `False` | Must be `False` in production to prevent stack trace leaks. |
| `DJANGO_ALLOWED_HOSTS` | **Yes** | `api.example.com,your-app.onrender.com` | Comma-separated allowed hostnames for the API. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | **Yes** | `https://app.example.com,https://api.example.com` | Trusted origins for CSRF checks (must include `https://`). |
| `CORS_ALLOWED_ORIGINS` | **Yes** | `https://app.example.com` | Comma-separated list of origins allowed to make API requests. |
| `FRONTEND_URL` | **Yes** | `https://app.example.com` | Public base URL used in password reset links and emails. |
| `DATABASE_URL` | **Yes (Prod)** | `postgresql://user:pass@host:5432/dbname?sslmode=require` | Database connection URL (PostgreSQL recommended). |
| `DJANGO_DB_CONN_MAX_AGE` | No | `600` | Database persistent connection lifetime in seconds. |
| `DJANGO_SECURE_SSL_REDIRECT` | No | `True` | Redirect HTTP to HTTPS (set `False` if proxy handles it). |
| `DJANGO_SESSION_COOKIE_SECURE` | No | `True` | Transmit session cookies over HTTPS only. |
| `DJANGO_CSRF_COOKIE_SECURE` | No | `True` | Transmit CSRF cookies over HTTPS only. |
| `DJANGO_SECURE_HSTS_SECONDS` | No | `31536000` | HTTP Strict Transport Security (HSTS) duration in seconds. |
| `GEMINI_API_KEY` | Optional | `AIzaSy...` | Enables AI Tutor and Gemini-assisted code feedback. |
| `GEMINI_MODEL` | Optional | `gemini-2.0-flash` | Gemini model name. |
| `DJANGO_EMAIL_BACKEND` | No | `django.core.mail.backends.smtp.EmailBackend` | Email backend for production password resets. |
| `DJANGO_EMAIL_HOST` | Optional | `smtp.sendgrid.net` | SMTP host. |
| `DJANGO_EMAIL_PORT` | Optional | `587` | SMTP port. |
| `DJANGO_EMAIL_HOST_USER` | Optional | `apikey` | SMTP username. |
| `DJANGO_EMAIL_HOST_PASSWORD` | Optional | `your-smtp-password` | SMTP password / API token. |
| `DJANGO_EMAIL_USE_TLS` | Optional | `True` | Enable TLS for SMTP connections. |

### Frontend (`frontend/.env` or Static Hosting Environment)

| Variable | Required | Default / Example | Purpose |
|---|---|---|---|
| `VITE_API_BASE_URL` | **Yes (Prod)** | `https://api.example.com/api/` | Target backend API endpoint ending with `/api/`. |
| `VITE_SHOW_DEMO_CREDENTIALS` | No | `false` | Set `false` in production to hide demo autofill credentials. |

---

## 3. Deployment Option 1: PaaS (Render + Vercel)

### Backend on Render (Web Service):
1. Create a **New Web Service** connected to your GitHub repository.
2. Set **Root Directory** to `backend`.
3. Set **Runtime** to `Python 3`.
4. Set **Build Command**:
   ```bash
   pip install -r requirements.txt && python manage.py collectstatic --noinput
   ```
5. Set **Start Command**:
   ```bash
   python manage.py migrate && gunicorn exam_portal.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --threads 2 --timeout 120
   ```
6. Add all required environment variables under the **Environment** tab.
7. Set Health Check Path to `/healthz/`.

### Frontend on Vercel:
1. Create a **New Project** connected to the repository.
2. Set **Root Directory** to `frontend`.
3. Set **Framework Preset** to `Vite`.
4. Add Environment Variable:
   - `VITE_API_BASE_URL`: `https://<your-render-backend-url>/api/`
   - `VITE_SHOW_DEMO_CREDENTIALS`: `false`
5. Deploy. The included `vercel.json` automatically handles SPA routing.

---

## 4. Deployment Option 2: Linux VPS / Ubuntu Server (Nginx + Gunicorn + Systemd)

### Step 1: Install System Packages and Compilers
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip python3-dev postgresql postgresql-contrib \
    nginx git curl build-essential default-jdk nodejs npm certbot python3-certbot-nginx
```

### Step 2: Clone Repository & Setup Virtualenv
```bash
cd /var/www
sudo git clone https://github.com/your-org/AcademiaPro.git academiapro
sudo chown -R www-data:www-data /var/www/academiapro
cd /var/www/academiapro/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Configure Gunicorn Systemd Service
Create `/etc/systemd/system/academiapro-backend.service`:
```ini
[Unit]
Description=AcademiaPro Django Backend Gunicorn Daemon
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/academiapro/backend
ExecStart=/var/www/academiapro/backend/.venv/bin/gunicorn \
          --access-logfile - \
          --error-logfile - \
          --workers 3 \
          --threads 2 \
          --timeout 120 \
          --bind unix:/run/academiapro.sock \
          exam_portal.wsgi:application
EnvironmentFile=/var/www/academiapro/backend/.env
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start Gunicorn:
```bash
sudo systemctl daemon-reload
sudo systemctl start academiapro-backend
sudo systemctl enable academiapro-backend
```

### Step 4: Build Frontend
```bash
cd /var/www/academiapro/frontend
npm ci
VITE_API_BASE_URL=https://api.yourdomain.com/api/ VITE_SHOW_DEMO_CREDENTIALS=false npm run build
```

### Step 5: Configure Nginx Reverse Proxy & SSL
Create `/etc/nginx/sites-available/academiapro`:
```nginx
server {
    listen 80;
    server_name app.yourdomain.com api.yourdomain.com;

    location / {
        return 301 https://$host$request_uri;
    }
}

# Frontend SPA
server {
    listen 443 ssl http2;
    server_name app.yourdomain.com;

    root /var/www/academiapro/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Static caching
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, max-age=31536000, immutable";
    }
}

# Backend API
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    client_max_body_size 25M;

    location /static/ {
        alias /var/www/academiapro/backend/staticfiles/;
        expires 30d;
    }

    location /media/ {
        alias /var/www/academiapro/backend/media/;
        expires 7d;
    }

    location / {
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://unix:/run/academiapro.sock;
    }
}
```

Enable site and install SSL certificate:
```bash
sudo ln -s /etc/nginx/sites-available/academiapro /etc/nginx/sites-enabled/
sudo nginx -t
sudo certbot --nginx -d app.yourdomain.com -d api.yourdomain.com
sudo systemctl restart nginx
```

---

## 5. Deployment Option 3: Docker & Docker Compose

To deploy AcademiaPro using Docker:

1. Clone repository and create root `.env` from `.env.example`:
   ```bash
   cp .env.example .env
   ```
2. Build and start containers:
   ```bash
   docker compose up -d --build
   ```
3. Run database migrations:
   ```bash
   docker compose exec backend python manage.py migrate
   ```
4. Optional: Seed demo data:
   ```bash
   docker compose exec backend python seed_data.py
   ```
5. The application is now accessible at `http://localhost` (Frontend) and `http://localhost:8000/api/` (API).

---

## 6. Cloud Deployment Risks & Mitigations

| Risk Factor | Impact | Recommended Production Mitigation |
|---|---|---|
| **Ephemeral Filesystem on Serverless/PaaS** | Uploaded notes/recordings in `media/` are lost when containers restart on Render/Heroku. | Attach a persistent disk volume to `/app/media` or configure AWS S3 / Cloudflare R2 for media storage in enterprise setups. |
| **Long-Running Gemini API Calls** | Gateway timeouts (504) if code evaluation takes >30 seconds under heavy load. | Gunicorn timeout is configured to `--timeout 120`. Ensure load balancer / reverse proxy timeouts match (>=120s). |
| **CORS / CSRF Scheme Mismatches** | Login or POST requests fail with 403 Forbidden if scheme is missing or incorrect. | Always prefix origins with `https://` in `DJANGO_CSRF_TRUSTED_ORIGINS` and `CORS_ALLOWED_ORIGINS`. |
| **Reverse Proxy SSL Termination** | Django may enter infinite redirect loops if SSL redirects are enabled without proxy headers. | AcademiaPro includes `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` out of the box. |
| **Code Runner Sandbox Security** | Executing untrusted student code directly on the host OS. | For multi-tenant production hosting, run worker processes in isolated, unprivileged container sandboxes with memory/CPU cgroups. |

---

## 7. Post-Deployment Verification Checklist

- [ ] `DEBUG` is set to `False` in backend environment.
- [ ] Unique `DJANGO_SECRET_KEY` is configured and not exposed.
- [ ] Database migrations applied successfully: `python manage.py migrate`.
- [ ] Static files collected: `python manage.py collectstatic --noinput`.
- [ ] Health check endpoint responds: `curl -I https://api.yourdomain.com/healthz/` returns `200 OK`.
- [ ] Frontend successfully logs in and connects to backend API.
- [ ] Admin panel accessible at `/admin/` with strong superuser credentials.
- [ ] Automated tests run clean: `python manage.py test portal`.
