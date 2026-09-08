# Academia Pro Frontend

> A responsive assessment workspace for students, faculty, and administrators.

Academia Pro is an online exam portal built for secure assessments, result publishing, Gemini-assisted coding feedback, and transparent review workflows. This repository contains the React client.

## Highlights

- Student dashboard for upcoming, live, and completed assessments
- Secure exam room with proctoring controls and timed submissions
- Results, performance insights, and coding feedback
- Faculty assessment creation, roster review, marking, and appeals handling
- Admin pages for users, security/proctor reports, and audit logs
- Responsive navigation, notifications, light/dark theme, and JWT session handling

## Tech Stack

- React 18
- Vite 6
- React Router
- Axios
- Tailwind CSS and custom CSS
- Lucide React icons

## Project Structure

```text
src/
  api/          API client and JWT refresh handling
  components/   Shared navigation, notifications, and guards
  context/      Authentication and theme state
  pages/        Student, faculty, admin, and public pages
```

## Requirements

- Node.js 18 or later
- A running Academia Pro backend API

## Setup

```bash
npm install
```

Create `.env` in this folder when the API is not hosted on the default local address:

```env
VITE_API_BASE_URL=https://your-api.example.com/api/
```

For local development, `VITE_API_BASE_URL` is optional. The app automatically uses `http://localhost:8000/api/` while Vite runs on port `5173`.

## Run

```bash
npm run dev
```

Open `http://localhost:5173`.

## Build

```bash
npm run build
npm run preview
```

Deploy the generated `dist/` directory to any static host. Configure `VITE_API_BASE_URL` in the host's build environment to point to the deployed backend API, including its trailing `/api/` path.

## Main Features

- Role-aware student, faculty, and admin workspaces
- Secure assessment delivery, results, insights, and appeals
- Faculty paper creation and Gemini-assisted coding evaluation
- Admin user, security, and audit pages

## Related Repository

The Django REST API is maintained in the companion **Academia Pro Backend** repository. Configure `VITE_API_BASE_URL` to its deployed `/api/` endpoint.
