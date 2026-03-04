# Eventify â€“ AI Powered Sustainable Event Management System

This repository contains a full-stack application designed to reduce food waste and optimize logistics for events using machine learning.

## ðŸš€ Features

- Organizer registration with JWT authentication
- Event creation and QR code generation
- Guest RSVP pages and entrance scanning
- Machine learning models for attendance, food, parking, and room estimation
- SOS emergency system
- Sustainability analytics dashboard
- Dockerized backend, frontend, PostgreSQL, and Redis

## ðŸ› ï¸ Technology Stack

**Frontend**: Next.js (App Router), TypeScript, Tailwind CSS, Chart.js, Axios

**Backend**: Python 3.11, FastAPI, SQLAlchemy, Pydantic, JWT auth

**Machine Learning**: scikit-learn, XGBoost, pandas, numpy, joblib

**Database**: PostgreSQL

**DevOps**: Docker, docker-compose, environment variables

## ðŸ“ Project Structure

```
eventify/
â”‚
â”œâ”€â”€ backend/
â”‚   â”œâ”€â”€ main.py
â”‚   â”œâ”€â”€ database.py
â”‚   â”œâ”€â”€ config.py
â”‚   â”œâ”€â”€ requirements.txt
â”‚   â”œâ”€â”€ models/
â”‚   â”œâ”€â”€ schemas/
â”‚   â”œâ”€â”€ routes/
â”‚   â”œâ”€â”€ ml/
â”‚   â”œâ”€â”€ utils/
â”‚   â””â”€â”€ Dockerfile
â”‚
â”œâ”€â”€ frontend/
â”‚   â”œâ”€â”€ app/
â”‚   â”œâ”€â”€ components/
â”‚   â”œâ”€â”€ services/
â”‚   â”œâ”€â”€ package.json
â”‚   â”œâ”€â”€ tailwind.config.js
â”‚   â””â”€â”€ Dockerfile
â”‚
â”œâ”€â”€ docker-compose.yml
â”œâ”€â”€ .env.example
â”œâ”€â”€ setup.sh
â””â”€â”€ README.md
```

## ðŸ“¦ Getting Started

### With Docker

1. Copy `.env.example` to `.env` and fill in any needed values.
2. Run:
   ```bash
   docker-compose up --build
   ```
3. Backend available at `http://localhost:8000` and frontend at `http://localhost:3000`.

### Without Docker

1. **Backend**
   ```bash
   # ensure Python 3.11 is installed
   python -m venv venv
   source venv/bin/activate   # or venv\Scripts\activate on Windows
   pip install -r backend/requirements.txt
   export DATABASE_URL="postgresql://user:pass@localhost:5432/eventify"  # or use .env
   cd backend && uvicorn main:app --reload
   ```

2. **Frontend**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. **Initial ML models**
   You can generate sample models with:
   ```bash
   python - <<'PY'
import ml.model
model.train_sample_models()
PY
   ```

## ðŸ§ª Testing with Sample Data

A helper script creates an organizer, an event and guests:

```bash
cd backend && python -m sample_data
```

You can also use `curl` or Postman to hit the API endpoints. Example:

```bash
# register user
curl -X POST "http://localhost:8000/auth/register" -H "Content-Type: application/json" \
  -d '{"name":"Org","email":"org@example.com","password":"secret"}'
# predict attendance
curl -X POST "http://localhost:8000/predict/attendance" -H "Content-Type: application/json" -d '{"features":[1,2,3,4,5]}'
# retrain model
curl -X POST "http://localhost:8000/retrain/model"
```
## ðŸ” Security Notes

- Passwords are hashed using bcrypt
- JWT is used for authentication
- Environment variables are used for all secrets

## â˜ï¸ Deployment

The application is cloud-ready and compatible with AWS EC2, RDS, and S3. Avoid hardcoded secrets; use environment variables.

## âœ¨ Contributions

This is a starter scaffold for Eventify. Feel free to extend features, improve ML models, and add UI components.

---

Made with â¤ï¸ by Eventify AI team

