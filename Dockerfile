# ResQ — Responsive Emergency Systems Intelligence (Production Docker Image)
FROM python:3.12-slim

WORKDIR /app

# Set production environment flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose container port
EXPOSE 5000

# Execute multi-threaded Gunicorn binding to dynamically assigned $PORT
CMD ["sh", "-c", "gunicorn -k gthread --threads 100 --workers 1 --bind 0.0.0.0:${PORT:-5000} app:app"]

