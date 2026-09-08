# Academia Pro Backend

> REST API powering secure online assessments, role-based workflows, and Gemini-assisted coding evaluation.

Academia Pro is an examination portal for students, faculty, and administrators. This repository contains the Django API used by the React client.

## Highlights

- JWT authentication with student, faculty, and administrator roles
- Assessment scheduling, OTP access, timed attempts, and result publishing
- MCQ and coding-question workflows with Gemini-assisted evaluation
- Proctoring events, screen-recording uploads, and account-lock handling
- Appeals/ticket workflow with department-scoped faculty review
- Notifications, audit trails, PDF result cards, analytics, and CSV exports
- SQLite for local development and PostgreSQL support for deployment

## Tech Stack

- Python and Django
- Django REST Framework
- Simple JWT
- PostgreSQL / SQLite
- Google Gemini API
- Matplotlib and Seaborn analytics

## Project Structure

```text
exam_portal/  Django configuration and settings
portal/       Models, serializers, views, permissions, and API routes
portal/migrations/  Database migrations
manage.py     Django command entry point
```

## Requirements

- Python 3.10 or later
- PostgreSQL for production (SQLite is used automatically for local development)
- A Gemini API key for AI tutor and coding-evaluation features

## Setup

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` in this folder:

```env
DJANGO_SECRET_KEY=replace-with-a-long-random-secret
DJANGO_DEBUG=true
GEMINI_API_KEY=your-gemini-api-key
FRONTEND_URL=http://localhost:5173
CORS_ALLOWED_ORIGINS=http://localhost:5173
```

Optional PostgreSQL configuration:

```env
DATABASE_URL=postgresql://user:password@host:5432/database
```

Alternatively set `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGHOST`, and `PGPORT`.

## Run Locally

```bash
python manage.py migrate
python manage.py runserver
```

The API runs at `http://localhost:8000/api/`.

Create an administrative user when needed:

```bash
python manage.py createsuperuser
```

## Checks

```bash
python manage.py check
python manage.py test
```

## Production

Set `DJANGO_DEBUG=false`, configure `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `FRONTEND_URL`, and a PostgreSQL `DATABASE_URL`. Apply migrations during deployment:

```bash
python manage.py migrate
gunicorn exam_portal.wsgi:application
```

Never commit `.env`, credentials, API keys, or the SQLite database to a public repository.

## Related Repository

The React web application is maintained in the companion **Academia Pro Frontend** repository. Set `FRONTEND_URL` and `CORS_ALLOWED_ORIGINS` to the deployed frontend URL.
