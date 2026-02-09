#!/bin/bash
python manage.py migrate
python manage.py collectstatic --noinput
python scripts/create_superuser.py
gunicorn --bind=0.0.0.0:8000 config.wsgi:application
