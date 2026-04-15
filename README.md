# Auth Blog Backend 🚀

Una plataforma de blog moderna y escalable construida con Django REST Framework, con autenticación robusta, gestión de contenido, análisis en tiempo real y características empresariales.

## 📋 Tabla de Contenidos

- [Características](#características)
- [Stack Tecnológico](#stack-tecnológico)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Requisitos Previos](#requisitos-previos)
- [Instalación](#instalación)
- [Configuración](#configuración)
- [Ejecución](#ejecución)
- [API Endpoints](#api-endpoints)
- [Docker](#docker)
- [Celery & Tasks](#celery--tasks)
- [Contribuir](#contribuir)

---

## ✨ Características

### 🔐 Autenticación & Seguridad

- **Autenticación JWT**: Tokens seguros con SimpleJWT
- **OTP (One-Time Password)**: Autenticación de dos factores con códigos QR
- **Rate Limiting**: Protección contra fuerza bruta con Django Axes
- **Password Hashing**: Encriptación de contraseñas con Argon2
- **Roles & Permisos**: Sistema de roles (Admin, Moderator, Editor)
- **Email Verification**: Confirmación de email al registro

### 📝 Gestión de Blog

- **Posts con Rich Text**: Editor WYSIWYG con TinyMCE
- **Categorías Jerárquicas**: Soporte para subcategorías
- **Slug URLs**: URLs amigables y SEO-friendly
- **Posts Destacados**: Destacar contenido importante
- **Full-Text Search**: Búsqueda avanzada de contenido

### 📊 Analytics & Interacciones

- **Post Analytics**: Tracking de vistas, likes y comentarios
- **Interacciones Registradas**: Historial de engagement por día
- **Vista por IP**: Análisis de visitantes únicos
- **Estadísticas en Tiempo Real**: Dashboard de métricas

### 📨 User Management

- **Perfiles de Usuario**: Información extendida del usuario
- **Social Links**: Instagram, Twitter, LinkedIn, etc.
- **Seguimiento de Login**: IP de login y OTP tracking
- **Avatar/Thumbnail**: Gestión de imágenes de perfil

### 📬 Newsletter

- **Suscripción**: Sistema de newsletter integrado
- **Campañas**: Gestión de suscriptores y envíos

### 📁 Media Management

- **Google Cloud Storage**: Almacenamiento en la nube
- **Optimización de Imágenes**: Compression y resizing
- **Gestión de Archivos**: Carga y descarga centralizada

### ⚡ Características Avanzadas

- **WebSockets con Channels**: Comunicación en tiempo real
- **Celery & Redis**: Cola de tareas asincrónicas
- **Cache Distribuido**: Redis para caching
- **CORS Configurado**: Soporte para múltiples dominios
- **Whitenoise**: Serving de archivos estáticos optimizado

---

## 🛠️ Stack Tecnológico

### Backend Framework
- **Django 5.2.12** - Web framework
- **Django REST Framework 3.16.1** - API REST
- **Uvicorn 0.38.0** - ASGI server

### Autenticación & Seguridad
- **djangorestframework-simplejwt 5.5.1** - JWT authentication
- **djoser 2.3.3** - User registration & auth endpoints
- **argon2-cffi 25.1.0** - Password hashing
- **django-axes 8.0.0** - Rate limiting & login attempts
- **pyotp 2.9.0** - OTP authentication

### Base de Datos & Cache
- **PostgreSQL** - SQL database
- **Django Redis 6.0.0** - Redis cache backend
- **Channels Redis 4.3.0** - Redis channel layer

### Procesamiento de Datos
- **Celery 5.6.0** - Task queue
- **Django Celery Results 2.6.0** - Celery results backend
- **Django Celery Beat 2.8.0** - Celery scheduler
- **Faker 38.0.0** - Generación de datos de prueba

### Almacenamiento & Archivos
- **django-storages 1.14.6** - Storage backend
- **google-cloud-storage 3.1.0** - Google Cloud Storage
- **Pillow 12.0.0** - Image processing
- **WhiteNoise 6.10.0** - Static files serving

### Frontend & Rich Text
- **Django TinyMCE 5.0.0** - Rich text editor
- **BeautifulSoup4 4.14.3** - HTML parsing
- **Bleach 6.3.0** - HTML sanitization
- **QRCode 8.2** - QR generation

### DevOps & Deployment
- **Docker & Docker Compose** - Containerización
- **django-environ 0.12.0** - Environment variables
- **django-cors-headers 4.9.0** - CORS handling
- **psycopg2 2.9.11** - PostgreSQL adapter

---

## 📦 Requisitos Previos

- **Python 3.13+**
- **pip** o **poetry**
- **Docker & Docker Compose** (opcional pero recomendado)
- **PostgreSQL 12+** (o usar Docker)
- **Redis** (o usar Docker)
- **Git**

---

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone <repository-url>
cd auth-blog/backend
```

### 2. Crear un entorno virtual

```bash
# Windows
python -m venv env
env\Scripts\activate

# Linux/Mac
python3 -m venv env
source env/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Crear un archivo `.env` en el directorio raíz:

```env
# Django Settings
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=
ENVIRONMENT=

# Database
DB_ENGINE=
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=
DB_PORT=

# Redis
REDIS_URL=

# JWT
JWT_SECRET=
JWT_ALGORITHM=
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=
JWT_REFRESH_TOKEN_EXPIRE_DAYS=

# Email Configuration
EMAIL_BACKEND=
EMAIL_HOST=
EMAIL_PORT=
EMAIL_USE_TLS=
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=

# CORS Settings
CORS_ALLOWED_ORIGINS=
CSRF_TRUSTED_ORIGINS=

# Google Cloud Storage
GCS_BUCKET_NAME=
GOOGLE_APPLICATION_CREDENTIALS=

# API Keys
VALID_API_KEYS=

# Celery
CELERY_BROKER_URL=
CELERY_RESULT_BACKEND=
```

---

## ⚙️ Configuración

### Migraciones de Base de Datos

```bash
# Crear migraciones
python manage.py makemigrations

# Aplicar migraciones
python manage.py migrate

# Crear superuser
python manage.py createsuperuser
```

### Crear datos de prueba (opcional)

```bash
python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> from faker import Faker
>>> # Crear usuarios y posts de prueba
```

### Configurar Google Cloud Storage (opcional)

1. Descargar credenciales JSON de GCP
2. Guardar en `secrets/gcs-credentials.json`
3. Configurar variables de entorno necesarias

---

## 🏃 Ejecución

### Modo Desarrollo (Local)

```bash
# Iniciar servidor Django (con Uvicorn)
python manage.py runserver

# O con Uvicorn directamente
uvicorn core.asgi:application --reload --host 0.0.0.0 --port 8000
```

La API estará disponible en: `http://localhost:8000`

### Iniciar Celery Worker

En una terminal separada:

```bash
celery -A core worker --loglevel=info
```

### Iniciar Celery Beat (Scheduler)

En otra terminal:

```bash
celery -A core beat --loglevel=info
```

---

## 🐳 Docker

### Iniciar con Docker Compose

```bash
# Construir imágenes
docker-compose build

# Iniciar servicios
docker-compose up -d

# Ver logs
docker-compose logs -f

# Detener servicios
docker-compose down
```

### Servicios en Docker Compose

- **blog_backend**: Django app en puerto 8000
- **blog_django_db**: PostgreSQL en puerto 5433
- **blog_django_redis**: Redis en puerto 6379
- **celery_worker**: Worker de Celery

### Ejecutar migraciones en Docker

```bash
docker-compose exec blog_backend python manage.py migrate
```

### Crear superuser en Docker

```bash
docker-compose exec blog_backend python manage.py createsuperuser
```

---

## 📡 API Endpoints

### Autenticación

```
POST   /api/auth/register/          - Registrar usuario
POST   /api/auth/login/             - Login con email/password
POST   /api/auth/token/             - Obtener JWT token
POST   /api/auth/token/refresh/     - Refrescar token
POST   /api/auth/logout/            - Logout usuario
POST   /api/auth/otp/setup/         - Setup OTP (2FA)
POST   /api/auth/otp/verify/        - Verificar OTP
GET    /api/auth/user/              - Obtener usuario actual
PUT    /api/auth/user/              - Actualizar usuario
POST   /api/auth/password/change/   - Cambiar contraseña
```

### Blog

```
GET    /api/blog/posts/             - Listar posts
POST   /api/blog/posts/             - Crear post
GET    /api/blog/posts/{id}/        - Detalle post
PUT    /api/blog/posts/{id}/        - Actualizar post
DELETE /api/blog/posts/{id}/        - Eliminar post

GET    /api/blog/categories/        - Listar categorías
POST   /api/blog/categories/        - Crear categoría

GET    /api/blog/comments/          - Listar comentarios
POST   /api/blog/comments/          - Crear comentario
```

### Perfil de Usuario

```
GET    /api/profile/                - Obtener perfil
PUT    /api/profile/                - Actualizar perfil
POST   /api/profile/avatar/         - Subir avatar
```

### Media

```
POST   /api/media/upload/           - Subir archivo
GET    /api/media/{id}/             - Descargar archivo
DELETE /api/media/{id}/             - Eliminar archivo
```

### Newsletter

```
POST   /api/newsletter/subscribe/   - Suscribirse
POST   /api/newsletter/unsubscribe/ - Desuscribirse
```

---

## ⚡ Celery & Tasks

### Tasks Disponibles

```python
# En apps/blog/tasks.py
- generate_post_thumbnail()
- send_newsletter_email()
- cleanup_old_sessions()

# En core/tasks.py
- send_async_email()
- cleanup_temporary_files()
```

### Ejecutar Task Manualmente

```python
from apps.blog.tasks import generate_post_thumbnail
generate_post_thumbnail.delay(post_id)
```

### Monitorear Celery

```bash
# Instalar flower (opcional)
pip install flower

# Ejecutar Flower
celery -A core flower --port=5555
```

Acceder a: `http://localhost:5555`

---

## 📊 Admin Panel

Acceder a: `http://localhost:8000/admin/`

Con credenciales de superuser creado.

---

## 🔐 Seguridad

### Best Practices Implementadas

✅ JWT tokens para autenticación stateless
✅ Argon2 para password hashing
✅ CORS configurado correctamente
✅ Rate limiting con Axes
✅ OTP para 2-factor authentication
✅ HTML sanitization con Bleach
✅ Environment variables para secrets
✅ HTTPS ready (configurar en producción)

---

## 🛠️ Development Workflow

### Crear nueva app

```bash
python manage.py startapp apps.<app_name>
```

### Crear migraciones

```bash
python manage.py makemigrations
python manage.py migrate
```

### Limpiar caché Redis

```python
from django.core.cache import cache
cache.clear()
```

### Resetear base de datos

```bash
python manage.py flush
python manage.py migrate
```

---

## 👨‍💻 Autor

Desarrollado por Nigel Ferreres como proyecto educativo para Udemy Django REST.

---


