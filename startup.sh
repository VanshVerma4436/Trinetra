#!/bin/bash

# 1. Install dependencies
python -m pip install -r requirements.txt

# 2. Collect Static Files (CSS/JS)
python manage.py collectstatic --noinput

# 3. Apply Database Migrations (CRITICAL: Creates/Updates tables)
python manage.py migrate

# 4. Start the Server (Gunicorn)
# Increases timeout to 600s because AI requests can be slow
gunicorn --bind=0.0.0.0:8000 --timeout 600 config.wsgi:application
