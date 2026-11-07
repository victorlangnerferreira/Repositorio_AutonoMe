FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    COOKIE_SECURE=true \
    AUTONOME_HOST=0.0.0.0

WORKDIR /app
COPY . .

EXPOSE 8000
CMD ["python", "server.py"]
