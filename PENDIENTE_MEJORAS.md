# 📋 TAREAS PENDIENTES Y AUDITORÍA — Asistente Comunal CPPO
**Última actualización:** 31 de octubre de 2026  
**Estado:** ✅ Auditoría integral aplicada (prioridades alta y media resueltas)  
**Basado en:** Revisión integral de seguridad, arquitectura y dependencias (f6d173c)

---

## ✅ MEJORAS DE AUDITORÍA COMPLETADAS (31/10/2026)

### Seguridad y Control de Acceso
- [x] **Autenticación robusta y efectiva:**
  - `API_KEY` se compara mediante `hmac.compare_digest` para evitar ataques de temporización (timing attacks).
  - `SERVER_HOST` fijado por defecto en `127.0.0.1` (localhost) en lugar de exponerse a toda la red por defecto.
  - `frontend/index.html` envía la cabecera `Authorization: Bearer <API_KEY>` desde `localStorage` en `apiFetch` y solicita la clave si recibe 401.
  - Rutas estáticas de documentos sensibles (`/cartas`, `/informes`, `/media/actas`) protegidas con autenticación cuando `API_KEY` está activa.
- [x] **Protección contra Path Traversal en `/api/universal/carpeta`:**
  - Verificación estricta con `is_relative_to(DOCUMENTOS_PATH)` para impedir lectura de rutas del sistema fuera del directorio comunal.
- [x] **Seguridad en Telegram Bot:**
  - `TELEGRAM_CHAT_ID` es obligatorio en `.env` para iniciar el bot.
  - `es_chat_autorizado` rechaza mensajes de remitentes no configurados (eliminada la auto-vinculación insegura).
- [x] **Sanitización y límites de subida de archivos:**
  - `backend/actas.py`: Sanitización de nombre de archivo con `Path(filename).name` para prevenir path traversal en Windows, y límite de 25 MB en PDFs.
  - `backend/proyectos.py`: Límite de 20 MB en archivos Word `.docx`.
- [x] **Privacidad de datos ante IA externa:**
  - Enmascaramiento de cédulas de identidad (`_enmascarar_cedula`) en voceros y censo demográfico antes de enviar contextos a APIs externas (NVIDIA, Zhipu, Gemini, Cohere, HuggingFace), protegiendo la identidad de la comunidad.
- [x] **Fugas de información mitigadas:**
  - `/api/status` ya no expone rutas absolutas del disco; devuelve el estado de disponibilidad y nombre del directorio.
  - `upload-photo` devuelve ruta relativa (`/media/...`) en lugar de rutas absolutas de Windows.
  - Manejo de excepciones 500 sin volcado de `detail=str(e)`.

### Bugs y Arquitectura
- [x] **Corrección de bug en Google Calendar (`calendar_sync.py`):**
  - Importación global de `datetime` y `timedelta` a nivel de módulo, resolviendo el `NameError` que impedía la sincronización de tareas.
- [x] **PWA 100% Offline y Recursos Locales:**
  - Movidos `lucide.js` y `chart.js` a `frontend/` y cargados localmente en `index.html` (sin dependencia de CDNs externos ni riesgo de SRI).
  - Eliminado el archivo huérfano `frontend/app.js`.
- [x] **Actualización y fijación de dependencias (`requirements.txt`):**
  - `Pillow` actualizado a versión segura `13.0.0` (probado con matplotlib y pytesseract).
  - Versiones fijadas para `fastapi==0.162.0`, `uvicorn[standard]==0.54.0`, `python-multipart==0.0.32`, `python-dotenv==1.2.4`.
- [x] **Índices de base de datos SQLite:**
  - Agregados índices `idx_voceros_consejo`, `idx_voceros_cedula`, `idx_voceros_cargo`, `idx_actividades_fecha`, `idx_cartas_fecha`, `idx_tareas_fecha`, `idx_actas_consejo`, `idx_documentos_hash`.

---

## 🟡 PENDIENTES A FUTURO (Mediano y largo plazo)

### Frontend & UI
- [ ] **Modularización de `index.html`:**
  - El archivo cuenta con más de 3.000 líneas de HTML y JS embebido; en futuras fases convendría modularizar componentes o migrar a Vue 3 / Vite.
- [ ] **Revisión profunda de `innerHTML`:**
  - Continuar asegurando que todas las variables dinámicas pasen por `escapeHTML()` antes de inyectarse.

### Agente IA & Automatizaciones
- [ ] **Cache de consultas frecuentes:**
  - Implementar cache LRU de 5 minutos para preguntas repetidas sobre voceros y padrón.
- [ ] **Alertas proactivas:**
  - Notificación proactiva cuando los periodos estatutarios de vocerías estén por vencerse.

### Infraestructura
- [ ] **Configuración de arranque en producción:**
  - `start.bat` o servicio de Windows con uvicorn en modo producción (`reload=False` y workers).
