# Sustainova - Sustainable Event Management System

Sustainova is a full-stack platform for sustainable wedding and event operations with FastAPI, Next.js, Supabase PostgreSQL, Docker, QR-based guest registration, and organizer dashboards.

## Features

- Organizer registration and JWT authentication
- Event creation and QR invitation flow
- Guest RSVP and check-in workflows
- QR-based entrance handling
- SOS emergency alerts
- Organizer dashboard and analytics
- ML-powered planning support (attendance, food, parking, room estimation)

## Tech Stack

- Frontend: Next.js (App Router), TypeScript, Tailwind CSS
- Backend: FastAPI, SQLAlchemy, Pydantic
- Database: Supabase PostgreSQL
- Infra: Docker, Docker Compose, Redis

## Project Structure

```text
sustainova/
|-- backend/
|-- frontend/
|-- docker-compose.yml
|-- .env.example
|-- setup.sh
`-- README.md
```

## Run With Docker

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000

## Run Without Docker

1. Backend

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r backend/requirements.txt
export DATABASE_URL="postgresql://user:pass@localhost:5432/sustainova"
cd backend && uvicorn main:app --reload
```

2. Frontend

```bash
cd frontend
npm install
npm run dev
```

## Environment

Use `.env` with your Supabase/PostgreSQL credentials. Example DB name has been renamed to `sustainova`.

## Branding

All project branding has been updated to Sustainova.

---

Sustainova - Sustainable Event Management System

