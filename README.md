# ShugoTime

Sistema web de gestión y monitoreo de relojes biométricos ZK para la **DPOSS — Dirección Provincial de Obras y Servicios Sanitarios de Ushuaia**.

Permite leer los registros de asistencia del personal desde múltiples relojes conectados en red y almacenarlos en la base de datos de personal existente.

---

## Funcionalidades

- **Gestión de relojes**: alta, baja y configuración de dispositivos ZK (IP, puerto, contraseña)
- **Ciclos de lectura**: lectura manual o programada de todos los relojes en background con seguimiento en tiempo real
- **Fichadas**: consulta de registros de asistencia filtrada por empleado, nombre, fecha y reloj
- **Tareas programadas**: crons configurables para lectura automática periódica
- **Logs operativos**: historial detallado de operaciones con éxitos, advertencias y errores por reloj
- **Acciones directas por reloj**: ping de conectividad, reinicio remoto y lectura individual

## Roles de usuario

| Rol | Acceso |
|---|---|
| **Invitado** (sin login) | Dashboard y consulta de fichadas |
| **Administrador** (con login) | Todo lo anterior + gestión de relojes, lectura de ciclos, logs y tareas programadas |

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Django 4.2 + Django REST Framework |
| Base de datos local | SQLite (configuración de relojes, ciclos, logs) |
| Base de datos de fichadas | PostgreSQL externo (sistema de personal existente) |
| Protocolo ZK | `pyzk` |
| Scheduler | APScheduler 3.x |
| Servidor | Gunicorn + WhiteNoise |
| Frontend | JavaScript vanilla (SPA) |
| Contenedores | Docker + Docker Compose |

---

## Requisitos

- Docker y Docker Compose
- Acceso de red a los relojes ZK
- Acceso a la base de datos PostgreSQL de personal

---

## Configuración

Copiá el archivo de ejemplo y completá los valores:

```bash
cp .env.example .env
```

### Variables de entorno

| Variable | Descripción | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Clave secreta de Django | *(cambiar en producción)* |
| `DJANGO_DEBUG` | Modo debug (`true`/`false`) | `true` |
| `SQLITE_PATH` | Ruta al archivo SQLite de la app | `/app/data/db.sqlite3` |
| `FICHADAS_DIR` | Directorio de backups de fichadas (txt) | `/app/data/fichadas` |
| `FICHADAS_DB_HOST` | Host del PostgreSQL de personal | `192.168.0.150` |
| `FICHADAS_DB_PORT` | Puerto del PostgreSQL de personal | `6003` |
| `FICHADAS_DB_NAME` | Nombre de la base de datos | `postgres` |
| `FICHADAS_DB_USER` | Usuario de la base de datos | `postgres` |
| `FICHADAS_DB_PASSWORD` | Contraseña de la base de datos | — |
| `FICHADAS_DB_OPTIONS` | Opciones de conexión (ej. search_path) | `-c search_path=public` |

---

## Instalación y ejecución

### Desarrollo

```bash
docker compose up --build
```

### Producción

```bash
./deploy.sh
```

El script `deploy.sh`:
1. Verifica que exista el archivo `.env`
2. Hace `git pull` para actualizar el código
3. Reconstruye y reinicia el contenedor con el perfil de producción
4. Limpia imágenes Docker viejas

El servicio queda expuesto en el puerto `8000` y se integra con Nginx Proxy Manager a través de la red externa `nginx-proxy-manager_npm-net`.

---

## Estructura del proyecto

```
ShugoTime/
├── backend/
│   ├── config/          # Configuración de Django (settings, urls, wsgi)
│   ├── relojes/         # App principal (modelos, vistas, API)
│   ├── templates/       # Frontend (HTML + JS)
│   ├── requirements.txt
│   └── entrypoint.sh    # Migraciones + arranque de Gunicorn
├── data/                # Volumen persistente (SQLite + backups de fichadas)
├── Dockerfile
├── docker-compose.yml
├── docker-compose.prod.yml
├── docker-compose.override.yml
└── deploy.sh
```

---

## API REST

Todos los endpoints bajo `/api/`:

| Endpoint | Descripción |
|---|---|
| `GET/POST /api/relojes/` | Listado y creación de relojes |
| `GET /api/ciclos/` | Historial de ciclos de lectura |
| `GET /api/logs/` | Logs de operaciones |
| `GET /api/fichadas/` | Consulta de registros de asistencia |
| `GET/POST /api/tareas/` | Gestión de tareas programadas |
| `GET /api/estado/` | Estado general del sistema |
| `POST /api/login/` | Autenticación |
| `POST /api/logout/` | Cierre de sesión |
| `GET /api/me/` | Usuario autenticado actual |
