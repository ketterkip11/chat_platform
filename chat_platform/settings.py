"""
Django settings for chat_platform project.
"""
import os
import dj_database_url
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# It is best practice to pull the secret key from the Render environment variables
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-0!8nl@i=8%+y_quat3cykbty8esqq$qud57hd35q$55l-g#ux9')
DEBUG = False

ALLOWED_HOSTS = ['chat-platform-qhc5.onrender.com', 'localhost', '127.0.0.1', '*']
CSRF_TRUSTED_ORIGINS = ['https://chat-platform-qhc5.onrender.com']

INSTALLED_APPS = [
    'daphne',
    'jazzmin',                 
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'customercare_chat',
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
]

ROOT_URLCONF = 'chat_platform.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], 
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'customercare_chat.context_processors.agent_unread', 
            ],
        },
    },
]

WSGI_APPLICATION = 'chat_platform.wsgi.application'
ASGI_APPLICATION = 'chat_platform.asgi.application'

# Configured for Render Redis
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379')],
        },
    },
}

# Configured for Render PostgreSQL
DATABASES = {
    'default': dj_database_url.config(default='sqlite:///db.sqlite3', conn_max_age=600)
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "chat"
LOGOUT_REDIRECT_URL = "login"

# ==========================================
# STATIC & MEDIA FILE CONFIGURATION
# ==========================================
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# This tells Django where to find your custom root static folder
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ==========================================
# JAZZMIN ADMIN CONFIGURATION
# ==========================================
JAZZMIN_SETTINGS = {
    "site_title": "Support Admin",
    "site_header": "Support Admin",
    "site_brand": "Customer Care",
    "welcome_sign": "Welcome to the Support Console",
    "search_model": ["auth.User", "customercare_chat.Conversation"],
    "show_ui_builder": False,
    "topmenu_links": [
        {"name": "Home",  "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "View Live Queue", "url": "agent_inbox", "new_window": True},
    ],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "customercare_chat.Conversation": "fas fa-comments",
        "customercare_chat.ChatMessage": "fas fa-envelope",
        "customercare_chat.AgentStatus": "fas fa-headset",
    },
}

JAZZMIN_UI_TWEAKS = {
    "navbar": "navbar-white navbar-light",
    "theme": "lumen", 
    "sidebar": "sidebar-dark-primary", 
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": True,
    "accent": "accent-primary", 
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    }
}