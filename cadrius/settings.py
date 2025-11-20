import os
from pathlib import Path
from dotenv import load_dotenv
import environ


# Inicializa django-environ
env = environ.Env(
    # Define valores padrão e tipos esperados
    DEBUG=(bool, False),
    SECRET_KEY=(str, 'INSECURE-DEFAULT-CHANGE-ME'),
    # Força o uso de URL de DB para Postgres/SQLite
    DATABASE_URL=(str, 'sqlite:///db.sqlite3'), 
)

# Carrega as variáveis do arquivo .env (se existir)
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
# Jullio: Esta deve vir do .env
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'default-insecure-key-for-local-dev-change-it')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['*'] # Para desenvolvimento local, pode ser '*'


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_yasg',
    'django_q', # Thales: Nosso broker de tarefas

    # Local apps (Jullio - Defina conforme o plano)
    'core',
    'emails',
    'integrations',
    'extraction',
    'tasks',
    
    'corsheaders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'cadrius.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'cadrius.wsgi.application'


# Database
# Jullio: Configuração para usar SQLite localmente.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
# Sugestão: Usar django-environ ou dj-database-url para configurar Postgres
# em staging/prod lendo a variável DATABASE_URL.


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    # ... configurações de validação de senha
]


# Internationalization
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Django REST Framework Settings ---
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}

# --- JWT Settings (Jullio) ---
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=5),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
}

# --- OpenAPI/Swagger Settings (Jullio) ---
SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header'
        }
    },
    'USE_SESSION_AUTH': False, # Desativa autenticação por sessão para APIs
}

# --- Django-Q Settings (Thales) ---
Q_CLUSTER = {
    # 1. Configuração do ORM Broker (usa o banco de dados principal)
    'name': 'DjangORM',
    'workers': 4, # Número de processos worker
    'timeout': 90, # Timeout para tarefas longas (segundos)
    'retry': 120, # Tempo para retry (segundos)
    'queue_limit': 50, # Limite de tarefas na fila
    'bulk': 10, # Número de tarefas puxadas de uma vez
    'log_level': 'INFO',
    'orm': 'default', # Usa a configuração 'default' do DATABASE
}

# --- Configurações das Integrações (Juliano/Thales) ---

# OPENAI (Juliano)
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo')

# TRELLO (Thales)
TRELLO_API_KEY = os.environ.get('TRELLO_API_KEY')
TRELLO_API_TOKEN = os.environ.get('TRELLO_API_TOKEN')
TRELLO_BOARD_ID = os.environ.get('TRELLO_BOARD_ID')
TRELLO_LIST_ID = os.environ.get('TRELLO_LIST_ID')

# TELEGRAM (Thales)
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# IMAP/EMAIL (Thales)
IMAP_HOST = os.environ.get('IMAP_HOST')
IMAP_PORT = os.environ.get('IMAP_PORT', 993)
IMAP_USERNAME = os.environ.get('IMAP_USERNAME')
IMAP_PASSWORD = os.environ.get('IMAP_PASSWORD')



CORS_ALLOW_ALL_ORIGINS = False # Sempre defina como False em produção

# A lista de domínios/origens permitidas.
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    # Adicione aqui o seu domínio de produção/staging quando for o caso
]