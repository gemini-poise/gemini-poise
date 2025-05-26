FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY .env.example /app/.env
COPY . /app

EXPOSE 8000

CMD ["/bin/bash", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]