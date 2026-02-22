#!/bin/bash

# 1. Install dependencies
python -m pip install -r requirements.txt

# 2. Collect Static Files (CSS/JS)
python manage.py collectstatic --noinput

# 3. Apply Database Migrations (CRITICAL: Creates/Updates tables)
python manage.py migrate

# 4. Start the Server (Gunicorn)
# --timeout 600 : AI requests to Hugging Face can take up to 2 minutes
# --workers 2   : One worker serves web requests while the other waits for AI
# --threads 4   : Handle multiple concurrent connections per worker
gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 2 --threads 4 config.wsgi:application
