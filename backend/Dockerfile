FROM python:3.11-slim
ENV PYTHONPATH=/app

WORKDIR /app

# copy requirements and install
COPY requirements.txt .
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=180 \
    PIP_RETRIES=10

RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir --retries 10 --timeout 180 --progress-bar off -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
