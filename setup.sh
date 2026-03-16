#!/bin/bash
# Auto installation script for Sustainova
set -e

echo "Creating Python virtual environment..."
python -m venv venv
source venv/bin/activate

echo "Installing backend requirements..."
pip install --upgrade pip
pip install -r backend/requirements.txt

echo "Installing frontend dependencies..."
cd frontend
npm install
cd ..

# set up database
echo "Setting up PostgreSQL (assumes running instance or docker-compose)"
if [ -f ./.env ]; then
  export $(grep -v '^#' .env | xargs)
fi

python - <<'PY'
import ml
ml.model.train_sample_models()
print('Initial ML models created')
PY

echo "Setup complete. To start servers manually:"
echo "  (1) Activate virtualenv: source venv/bin/activate"
echo "  (2) Run backend: uvicorn backend.main:app --reload"
echo "  (3) Run frontend: cd frontend && npm run dev"
echo "Or use docker-compose up --build"


