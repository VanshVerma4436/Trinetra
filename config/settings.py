from pathlib import Path
import os
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================================================================
# CORE CONFIGURATION
# ==============================================================================

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-change-me-in-production-trinetra-security-core')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Local Apps
    'access_control',
    'authentication',
    'audit_logs',
    'officer_portal',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # Trinetra Security Core
    'config.middleware.IPFortressMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    { 'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator', },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Session Config (Global)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 300 # 5 Minutes Auto-Logout

# ==============================================================================
# DATABASE & CLOUD CONFIGURATION
# ==============================================================================

# 1. Debug Mode
# Robust check: handles 'True', 'true', '1'
DEBUG = str(os.environ.get('DEBUG', 'False')).lower() in ['true', '1', 't']

# 2. Database
# Uses SQLite by default. If DATABASE_URL is present, utilizes it (PostgreSQL ready).
if 'DATABASE_URL' in os.environ:
    DATABASES = {
        'default': dj_database_url.config(conn_max_age=600, ssl_require=True)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# 3. Static Files
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# 4. Security Logic
if not DEBUG:
    # --- PRODUCTION MODE (False) ---
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

    CSRF_TRUSTED_ORIGINS = []

else:
    # --- DEBUG MODE (True) ---
    # Relaxed settings for debugging
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    TRINETRA_STRICT_FIREWALL = False

    ALLOWED_HOSTS = ['*']
    
    CSRF_TRUSTED_ORIGINS = [
        'http://127.0.0.1:9000', 
        'http://localhost:9000',
        'http://127.0.0.1:8000',
        'http://localhost:8000',
    ]

# ==============================================================================
# FINAL FORCE-FIX FOR AZURE
# ==============================================================================
# These settings run LAST to ensure Azure works even if DEBUG is on.

# Always allow the Azure URL
azure_host = 'trinetra.azurewebsites.net'
azure_origin = 'https://trinetra.azurewebsites.net'

if azure_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(azure_host)

if azure_origin not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(azure_origin)

# Ensure lists are clean (remove empty strings if any)
ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS if h.strip()]