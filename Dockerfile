FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias del sistema (OpenCV + etc.)
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Comando por defecto (se puede sobreescribir en Render)
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && celery -A albertidl worker --loglevel=info --pool=solo & gunicorn albertidl.wsgi:application --bind 0.0.0.0:\$PORT --workers 2"]