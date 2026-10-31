# 🏘️ Asistente Comunal — Comuna Productiva Presidente Obrero

> Sistema integral de gestión comunal con inteligencia artificial, bot de Telegram, generación de documentos y sincronización con Google Calendar.

---

## 📋 Descripción

El **Asistente Comunal** es una aplicación web de escritorio diseñada para apoyar la gestión administrativa y operativa de la **Comuna Productiva Presidente Obrero** (Mérida, Venezuela). Centraliza en una sola plataforma:

- Consultas inteligentes sobre documentos comunales mediante IA
- Registro y seguimiento de actividades comunales
- Generación automática de cartas y oficios con numeración CPPO
- Gestión del padrón de voceros y consejos comunales
- Tareas y recordatorios sincronizados con Google Calendar
- Bot de Telegram para gestión remota desde el celular

---

## 🚀 Características principales

| Módulo | Descripción |
|--------|-------------|
| 🤖 **Agente Universal IA** | Consultas en lenguaje natural sobre voceros, actas, cartas, actividades y documentos |
| 📂 **Búsqueda documental** | Indexación y búsqueda semántica en PDFs, DOCX, XLSX e imágenes (OCR) |
| 📝 **Generación de cartas** | Redacción automática de oficios, solicitudes, comunicados y actas |
| 📊 **Informes PDF** | Generación de reportes de actividades con gráficos estadísticos |
| 🗳️ **Padrón comunal** | Registro de consejos comunales y voceros (principales y suplentes) |
| 📅 **Calendario** | Gestión de tareas y recordatorios con sincronización a Google Calendar |
| 📱 **Bot de Telegram** | Acceso remoto completo: registrar actividades, fotos, consultas y tareas |
| 📈 **Dashboard** | Panel de KPIs con estadísticas del mes, actividades, cartas y voceros |
| 🗃️ **Actas digitales** | Gestión de actas de asambleas y resoluciones comunales |
| 👥 **Consultas populares** | Registro y seguimiento de consultas populares de la comunidad |

---

## 🛠️ Tecnologías

### Backend
- **[FastAPI](https://fastapi.tiangolo.com/)** — Framework web asíncrono (Python)
- **[Uvicorn](https://www.uvicorn.org/)** — Servidor ASGI de alto rendimiento
- **[SQLite + aiosqlite](https://github.com/omnilib/aiosqlite)** — Base de datos local asíncrona
- **[APScheduler](https://apscheduler.readthedocs.io/)** — Programador de tareas y notificaciones proactivas
- **[python-telegram-bot](https://python-telegram-bot.org/)** — Bot de Telegram

### Inteligencia Artificial (APIs gratuitas con rotación automática)
- **[Groq](https://groq.com/)** — LLM ultra-rápido (Llama 3)
- **[Google Gemini](https://ai.google.dev/)** — Modelo multimodal de Google
- **[Cohere](https://cohere.com/)** — Modelos de lenguaje y embeddings
- **[HuggingFace](https://huggingface.co/)** — Modelos open-source
- **[ZhipuAI](https://open.bigmodel.cn/)** — GLM-4 (alta cuota diaria)

### Procesamiento de documentos
- **PyMuPDF / pdfplumber** — Extracción de texto en PDFs
- **python-docx** — Documentos Word (.docx)
- **openpyxl / xlrd / pandas** — Hojas de cálculo Excel
- **pytesseract + Pillow** — OCR para imágenes escaneadas

### Servicios externos
- **Google Calendar API** — Sincronización de tareas y recordatorios
- **matplotlib** — Generación de gráficos en informes

### Frontend
- HTML5 + CSS3 + JavaScript Vanilla (SPA monolítica)
- Sin dependencias de frameworks externos

---

## 📁 Estructura del proyecto

```
Asistente_de_oficina/
├── backend/
│   ├── main.py              # Punto de entrada FastAPI, todos los endpoints principales
│   ├── config.py            # Configuración central (rutas, APIs, cuotas)
│   ├── database.py          # Inicialización y gestión de SQLite
│   ├── agent.py             # Agente de consultas sobre voceros y consejos
│   ├── universal_agent.py   # Agente universal con clasificación de intención
│   ├── ai_router.py         # Rotación automática entre APIs de IA
│   ├── search.py            # Búsqueda semántica en documentos indexados
│   ├── indexer.py           # Indexación de PDFs, DOCX, XLSX e imágenes
│   ├── pdf_extractor.py     # Extracción de texto con OCR fallback
│   ├── letters.py           # Generación de cartas y oficios con numeración CPPO
│   ├── reports.py           # Generación de informes PDF con estadísticas
│   ├── activities.py        # Registro y consulta de actividades comunales
│   ├── padron.py            # Gestión del padrón (consejos y voceros)
│   ├── actas.py             # Gestión de actas de asambleas
│   ├── consultas.py         # Registro de consultas populares
│   ├── calendar_sync.py     # Sincronización con Google Calendar
│   ├── scheduler.py         # Notificaciones proactivas y recordatorios automáticos
│   ├── telegram_bot.py      # Bot de Telegram con comandos y respuestas de IA
│   └── auth_google.py       # Autenticación OAuth2 con Google
├── frontend/
│   ├── index.html           # Interfaz web principal (SPA)
│   ├── app.js               # Lógica del cliente JavaScript
│   └── style.css            # Estilos de la interfaz
├── templates/               # Plantillas para generación de cartas
├── media/                   # Imágenes y fotos subidas
├── informes_generados/      # Informes PDF generados
├── cartas_generadas/        # Cartas y oficios generados
├── requirements.txt         # Dependencias Python
├── start.bat                # Inicio rápido (Windows CMD)
├── start.ps1                # Inicio rápido (Windows PowerShell)
├── .env                     # Variables de entorno (NO subir a Git)
└── credentials.json         # Credenciales Google OAuth2 (NO subir a Git)
```

---

## ⚙️ Instalación y configuración

### Prerrequisitos

- **Python 3.10+** (recomendado 3.11 o 3.12; el 3.13 puede tener limitaciones con algunas dependencias)
- **[Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)** instalado y en el PATH del sistema (para lectura de imágenes escaneadas)
- Cuenta de **Telegram** para el bot (opcional pero recomendado)
- Cuenta de **Google** para el calendario (opcional)

### 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd Asistente_de_oficina
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv
venv\Scripts\activate        # Windows CMD
# o
.\venv\Scripts\Activate.ps1  # PowerShell

pip install -r requirements.txt
```

### 3. Configurar variables de entorno

Crea el archivo `.env` en la raíz del proyecto con el siguiente contenido:

```env
# === Rutas ===
DOCUMENTOS_COMUNA_PATH=D:\ruta\a\documentos\de\la\comuna
DATABASE_PATH=backend/database.db
MEDIA_PATH=media
INFORMES_PATH=informes_generados
CARTAS_PATH=cartas_generadas
TEMPLATES_PATH=templates

# === Servidor ===
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000

# === API Key de seguridad (dejar vacío en desarrollo) ===
API_KEY=

# === APIs de IA (obtener las claves gratuitas en cada portal) ===
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...
COHERE_API_KEY=...
HUGGINGFACE_API_KEY=hf_...
ZHIPU_API_KEY=...

# === Telegram Bot ===
TELEGRAM_BOT_TOKEN=123456789:AAF...
TELEGRAM_CHAT_ID=               # Se auto-configura al primer mensaje

# === Google Calendar ===
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_CALENDAR_EMAIL=productivapresidenteobrero@gmail.com

# === Numeración de oficios ===
OFICIO_PREFIJO=CPPO
```

### 4. Configurar Google Calendar (opcional)

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un proyecto y habilita la **Google Calendar API**
3. Descarga el archivo `credentials.json` (OAuth 2.0) y colócalo en la raíz del proyecto
4. En el primer inicio, se abrirá el navegador para autorizar el acceso

### 5. Iniciar la aplicación

**Opción A — Script rápido (recomendado):**

```bat
start.bat
```
o en PowerShell:
```powershell
.\start.ps1
```

**Opción B — Manual:**

```bash
venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Luego abre el navegador en: **http://localhost:8000/**

---

## 🤖 Bot de Telegram

Una vez configurado el `TELEGRAM_BOT_TOKEN`, el bot se inicia automáticamente con el servidor.

### Comandos disponibles

| Comando | Descripción |
|---------|-------------|
| `/start` | Muestra bienvenida y lista de comandos |
| `/buscar [término]` | Busca en los documentos indexados |
| `/actividad [descripción]` | Registra una actividad comunal |
| `/tarea [detalles]` | Agrega una tarea al calendario |
| `/tareas` | Muestra las próximas tareas pendientes |

> **Tip:** Puedes enviar una foto con descripción y el bot registrará la actividad automáticamente con la imagen adjunta.

> **Tip:** Escribe cualquier pregunta en lenguaje natural (sin comandos) y el agente buscará en los documentos y la base de datos para responderla.

---

## 🔌 API REST — Endpoints principales

La documentación interactiva completa está disponible en:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### Endpoints clave

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/status` | Estado del sistema y cuotas de IA |
| `GET` | `/api/dashboard/stats` | KPIs del panel principal |
| `POST` | `/api/agent/query` | Consulta al agente universal de IA |
| `GET` | `/api/activities` | Listar actividades comunales |
| `POST` | `/api/activities` | Registrar nueva actividad |
| `POST` | `/api/letters` | Generar carta u oficio |
| `GET` | `/api/documents/search` | Buscar en documentos indexados |
| `POST` | `/api/documents/index` | Indexar carpeta de documentos |
| `GET/POST` | `/api/padron/consejos` | Gestión de consejos comunales |
| `GET/POST` | `/api/padron/voceros` | Gestión de voceros |
| `POST` | `/api/tasks` | Crear tarea con recordatorio |
| `GET` | `/api/tasks` | Listar tareas pendientes |
| `POST` | `/api/reports/generate` | Generar informe PDF de actividades |
| `GET/POST` | `/api/actas` | Gestión de actas de asamblea |

---

## 🧠 Sistema de IA con rotación de proveedores

El sistema gestiona automáticamente múltiples proveedores de IA con **cuotas diarias gratuitas**:

| Proveedor | Cuota diaria | Prioridad |
|-----------|-------------|-----------|
| ZhipuAI (GLM-4) | 5.000 req/día | 1° |
| Groq (Llama 3) | 14.400 req/día | 2° |
| Google Gemini | 1.500 req/día | 3° |
| Cohere | 1.000 req/día | 4° |
| HuggingFace | 1.000 req/día | 5° |

Cuando un proveedor agota su cuota, el sistema pasa automáticamente al siguiente. Esto garantiza **continuidad del servicio sin costo**.

---

## 📄 Generación de documentos

### Cartas y Oficios
- Numeración automática con formato `CPPO-2026-Nro.001`
- Tipos: Solicitud, Denuncia, Convocatoria, Oficio, Acta, Informe, Constancia, Comunicado
- Redacción asistida por IA según instrucciones del usuario
- Membrete automático con datos de la comuna

### Informes PDF
- Estadísticas de actividades por mes y categoría
- Gráficos de participación (matplotlib)
- Descarga directa desde el panel web

---

## 🔒 Consideraciones de seguridad

> **⚠️ Esta aplicación está diseñada para uso en red local.**
> Para exponer a internet, revisa el documento `SECURITY_ARCHITECTURE_REVIEW.md` antes de hacerlo.

- La `API_KEY` en `.env` protege todos los endpoints `/api/*` si está definida
- Las comparaciones de clave usan `secrets.compare_digest` (resistente a timing attacks)
- Las subidas de archivos validan extensión, Content-Type, tamaño y contenido real con Pillow
- La búsqueda universal de carpetas está limitada al árbol configurado en `DOCUMENTOS_COMUNA_PATH`
- Los archivos `.env`, `credentials.json`, `token.json` y la base de datos están en `.gitignore`

---

## 💾 Backup a GitHub

El script `_backup_to_github.ps1` automatiza los commits y push al repositorio de respaldo, excluyendo datos sensibles según el `.gitignore`.

```powershell
.\_backup_to_github.ps1
```

---

## 🗂️ Categorías de actividades soportadas

- Asamblea · Consulta Popular · Obra / Construcción · Jornada · Reunión
- Visita Institucional · Taller / Formación · Evento Cultural / Deportivo
- Rendición de Cuentas · Censo · Otro

---

## 🤝 Contribución

Este proyecto es de uso interno para la **Comuna Productiva Presidente Obrero**. Para proponer mejoras o reportar errores, usa el sistema de Issues del repositorio.

---

## 📜 Licencia

Proyecto de gestión comunal. Todos los derechos reservados.  
**Comuna Productiva Presidente Obrero**, Mérida, Venezuela.

---

*Desarrollado con ❤️ para el poder comunal venezolano.*
