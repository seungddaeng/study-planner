FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy app code
COPY backend /app/backend
COPY templates /app/templates

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Production server
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "backend.app:app"]
