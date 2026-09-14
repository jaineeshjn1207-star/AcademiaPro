# AcademiaPro — Digital Examination & Assessment Platform

[![Django](https://img.shields.io/badge/Django-5.x-green.svg)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-18.x-blue.svg)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-6.x-purple.svg)](https://vitejs.dev/)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.x-38B2AC.svg)](https://tailwindcss.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-336791.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

AcademiaPro is a full-stack, enterprise-grade digital examination and assessment management platform designed for educational institutions, universities, and technical academies. It delivers secure multi-format examinations, automated evaluation with Google Gemini AI assistance, proctoring integrity monitoring, code similarity detection, and publication-ready academic marksheets.

---

## 🌟 Key Platform Capabilities

### 🎓 For Students:
- **Assessment Workspace:** Timed exams with live countdowns, auto-save state, full-screen lock enforcement, and proctoring telemetry.
- **Dual-Mode Examination:** Integrated support for **Multiple Choice Questions (MCQ)** and multi-language **Coding Challenges** (Python, JavaScript, C++, Java) with instant compiler execution.
- **Academic Results & Marksheets:** Download publication-ready, print-friendly A4 vector PDF marksheets with performance mastery scales and digital verification IDs.
- **Transparent Appeals:** File dispute tickets for manual faculty review with progress tracking.
- **AI Tutor & Study Notes:** Access subject revision notes and interactive Gemini-powered academic tutoring.

### 👨‍🏫 For Faculty:
- **Assessment Studio:** Create and schedule rich examinations, configure mark distributions, randomize question banks, and set custom evaluation thresholds.
- **Automated & Manual Grading:** Gemini-assisted code feedback, rubric grading, and manual score overrides.
- **Academic Integrity & Code Similarity:** Deterministic token-normalized code similarity engine with comment stripping, $\mathcal{O}(1)$ length bounds pruning, and similarity heatmap detection.
- **Roster & Performance Analytics:** Export assessment rosters, CSV mark sheets, score distributions, and statistical performance summaries.

### 🛡️ For Administrators:
- **User & Role Management:** Student, Faculty, and Admin user lifecycle management with department and branch scoping.
- **Proctoring Audit Logs:** Real-time violation feeds (tab switching, full-screen exit, webcam telemetry).
- **System Health & Security:** Immutable audit logs, account blocking for disciplinary violations, and secure JWT session controls.

---

## 🏗️ Architecture & Technology Stack

```text
AcademiaPro Full-Stack
 ├── Frontend (React 18 SPA + Vite 6 + Tailwind CSS + Lucide Icons)
 └── Backend (Django 5 + Django REST Framework + SimpleJWT + WhiteNoise + Gemini AI)
      ├── Database: PostgreSQL (Production) / SQLite (Development)
      ├── Code Runner: Sandboxed subprocess execution for Python, Node, C++, Java
      ├── Similarity Engine: Deterministic token normalization & SequenceMatcher
      └── PDF Engine: Vector-drawn academic marksheets via Matplotlib
```

---

## 🚀 Local Development Quickstart

### Prerequisites
- **Python:** 3.10 or higher
- **Node.js:** 18 or higher (with npm)
- **Compilers (Optional for Code Execution):** `gcc`, `g++`, `default-jdk`, `nodejs`

---

### Step 1: Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create local environment file
cp .env.example .env

# Run database migrations
python manage.py migrate

# (Optional) Seed demo assessment and user data
python seed_data.py

# Start Django development server
python manage.py runserver
```

The backend API is now running at `http://localhost:8000/api/` (Health check: `http://localhost:8000/healthz/`).

---

### Step 2: Frontend Setup

```bash
# Open a new terminal and navigate to frontend directory
cd frontend

# Install node dependencies
npm install

# Create frontend environment file
cp .env.example .env

# Start Vite development server
npm run dev
```

The frontend application is now accessible at `http://localhost:5173`.

---

## 🔑 Demo Login Credentials (When Seeded)

| Role | Username | Password | Access / Capabilities |
|---|---|---|---|
| **Administrator** | `admin` | `admin123` | Full administrative control, proctoring logs, user management |
| **Faculty** | `faculty` | `faculty123` | Exam creation, grading studio, code similarity, appeals |
| **Student** | `student` | `student123` | Exam taking, results, PDF marksheets, AI tutor |

---

## 🧪 Automated Testing Suite

AcademiaPro includes comprehensive automated unit, integration, and security regression tests.

```bash
cd backend
python manage.py test portal
```

To run targeted test suites:
```bash
# Run similarity engine and PDF marksheet tests:
python manage.py test portal.tests.ProductOperationsTests

# Run authentication and permission tests:
python manage.py test portal.tests.AuthAndRoleTests
```

To build and verify the frontend bundle:
```bash
cd frontend
npm run build
```

---

## 🌐 Production Deployment

AcademiaPro is production-ready for deployment on **Render**, **Vercel**, **Ubuntu/VPS (Nginx + Gunicorn)**, and **Docker Containers**.

Refer to the comprehensive deployment guide:  
📖 **[DEPLOYMENT.md](DEPLOYMENT.md)**

### Quick Docker Launch:
```bash
cp .env.example .env
docker compose up -d --build
docker compose exec backend python manage.py migrate
```

---

## 📁 Repository Directory Structure

```text
exam_portal/
├── backend/                  # Django REST API service
│   ├── exam_portal/          # Project configuration, settings, WSGI/ASGI
│   ├── portal/               # Core application (models, views, serializers, tests)
│   │   ├── pdf_generator.py  # Vector PDF academic marksheet engine
│   │   ├── similarity.py     # Code similarity & integrity engine
│   │   ├── code_runner.py    # Sandboxed compiler execution
│   │   └── ai_tutor.py       # Gemini AI integration
│   ├── staticfiles/          # WhiteNoise collected static assets
│   ├── Dockerfile            # Multi-stage backend container definition
│   ├── requirements.txt      # Python dependencies
│   └── seed_data.py          # Database seeding script
├── frontend/                 # React 18 Single Page Application
│   ├── src/                  # Components, pages, contexts, hooks, and styles
│   │   ├── api/              # Axios HTTP client with JWT auto-refresh
│   │   ├── context/          # Authentication and theme contexts
│   │   └── pages/            # Student, faculty, and admin views
│   ├── Dockerfile            # Multi-stage frontend container definition
│   ├── nginx.conf            # Nginx SPA reverse proxy configuration
│   └── package.json          # Frontend dependencies & scripts
├── docker-compose.yml        # Orchestration for DB, backend, and frontend
├── DEPLOYMENT.md             # Production deployment manual
└── README.md                 # Project documentation
```

---

## 📄 License & Integrity

This project is licensed under the MIT License. Developed for robust and scalable academic assessment workflows.
