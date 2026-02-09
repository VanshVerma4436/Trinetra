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
# Default to True locally, set to False in production via Env Var
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# 2. Allowed Hosts
# Allow all in debug, otherwise restrict
if DEBUG:
    ALLOWED_HOSTS = ['*']
else:
    # Add localhost/127.0.0.1 for local production testing
    ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]').split(',')

# 3. Database
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

# 4. Security & Static Files
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

if not DEBUG:
    # --- PRODUCTION SETTINGS (AZURE) ---
    
    # 1. Host Configuration
    # We combine environment variable + hardcoded Azure URL to be safe
    env_hosts = os.environ.get('ALLOWED_HOSTS', '').split(',')
    ALLOWED_HOSTS = env_hosts + ['trinetra.azurewebsites.net']
    # Clean up empty strings
    ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS if h.strip()]

    # 2. CSRF Trust (CRITICAL FIX)
    # Explicitly trust the Azure HTTPS URL
    CSRF_TRUSTED_ORIGINS = [
        'https://trinetra.azurewebsites.net',
    ]

    # 3. SSL & Cookie Security
    # These MUST be True for HTTPS to work correctly
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    # Azure Load Balancer support (Trusts the SSL termination)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

else:
    # --- LOCAL DEVELOPMENT SETTINGS ---
    ALLOWED_HOSTS = ['*']
    
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    
    # Relaxed Security for Demo
    TRINETRA_STRICT_FIREWALL = False

    CSRF_TRUSTED_ORIGINS = [
        'http://127.0.0.1:9000', 
        'http://localhost:9000',
        'http://127.0.0.1:8000',
        'http://localhost:8000',
    ]