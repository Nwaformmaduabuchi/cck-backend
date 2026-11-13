
# 1. Start with Python 3.12 on Debian Bookworm
FROM python:3.12-slim-bookworm

# 2. Prevent Python from creating unnecessary cache files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# 3. Set the working directory inside the container
WORKDIR /app

# 4. Install Linux libraries required by WeasyPrint
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz-subset0 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy requirements first
COPY requirements.txt .

# 6. Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 7. Copy the Django application into the container
COPY . .

# 8. Create a non-root user for better security
RUN useradd --create-home appuser && \
    chown -R appuser:appuser /app

USER appuser

# 9. Start Django using Gunicorn
# Cloud Run supplies PORT; use 8080 locally if PORT is absent.
CMD ["sh", "-c", "gunicorn myproject.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 4 --timeout 120"]
