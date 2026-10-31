# 📋 TAREAS PENDIENTES Y AUDITORÍA — Asistente Comunal CPPO
**Última actualización:** 31 de octubre de 2026 (Segunda revisión verificada)  
**Estado:** ✅ Auditoría integral y verificación al 100% completadas  
**Basado en:** Revisión integral de seguridad, arquitectura y dependencias

---

## ✅ MEJORAS DE AUDITORÍA COMPLETADAS (31/10/2026)

### Seguridad y Control de Acceso (Fase 1 y 2)
- [x] **Mitigación del bypass en actas con barras dobles (`//`):**
  - En `backend/main.py`: `auth_middleware` ahora normaliza canónicamente las rutas con `posixpath.normpath(re.sub(r"/+", "/", raw_path))`, interceptando peticiones maliciosas como `/media//actas/...`, `/media/./actas/...` y variantes.
- [x] **Autenticación completa en frontend (compatibilidad con `API_KEY`):**
  - La subida de actas (`frontend/index.html`) migrada a `apiFetch`, enviando la cabecera `Authorization`.
  - Nueva función `abrirArchivoAutenticado(url, downloadName)`: Descarga mediante `fetch` autenticado con Bearer y abre o descarga a través de un Object URL Blob seguro, sin exponer tokens en la barra de direcciones ni en el historial.
  - Aplicado a cartas (PDF, DOCX, Imprimir), informes de gestión, gaceta comunal y exportaciones Excel del padrón.
- [x] **Scripts de arranque seguros (`start.bat` y `start.ps1`):**
  - Eliminado `--host 0.0.0.0` forzado. Ahora escuchan por defecto en `127.0.0.1` (localhost), respetando la variable `%SERVER_HOST%` / `$env:SERVER_HOST` si el administrador desea exponerlo explícitamente.
- [x] **Eliminación total de fugas de información interna (`detail=str(e)`):**
  - Saneados los 7 volcados de excepciones en `actas.py`, `gaceta.py`, `main.py`, `padron.py` y `proyectos.py`. Ahora se registra el detalle completo en `logger.error(..., exc_info=True)` y se entregan mensajes descriptivos y seguros al usuario.
- [x] **Documentación de Telegram en `README.md`:**
  - Actualizado para indicar que `TELEGRAM_CHAT_ID` es obligatorio en `.env` para evitar accesos no autorizados.
- [x] **Protección contra Path Traversal en `/api/universal/carpeta`:**
  - Verificación con `is_relative_to(DOCUMENTOS_PATH)` para impedir lectura de carpetas arbitrarias del servidor.
- [x] **Sanitización y límites de subida de archivos:**
  - `backend/actas.py`: Sanitización de nombre de archivo con `Path(filename).name` y límite de 25 MB.
  - `backend/proyectos.py`: Límite de 20 MB en archivos Word `.docx`.
- [x] **Privacidad de datos ante IA externa:**
  - Enmascaramiento de cédulas de identidad (`_enmascarar_cedula`) en voceros y censo demográfico antes de enviar contextos a APIs externas (NVIDIA, Zhipu, Gemini, Cohere, HuggingFace).

### Bugs y Rendimiento
- [x] **Corrección de bug en Google Calendar (`calendar_sync.py`):**
  - Importación global de `datetime` y `timedelta` a nivel de módulo.
- [x] **PWA 100% Offline y Recursos Locales:**
  - Movidos `lucide.js` y `chart.js` a `frontend/` y cargados localmente en `index.html`.
  - Eliminado el archivo huérfano `frontend/app.js`.
- [x] **Actualización de dependencias (`requirements.txt`):**
  - `Pillow` actualizado a `13.0.0` (eliminando más de 70 vulnerabilidades) y probado con matplotlib y pytesseract.
  - Versiones fijadas para `fastapi`, `uvicorn[standard]`, `python-multipart`, `python-dotenv`.
- [x] **Índices de base de datos SQLite:**
  - 8 índices activos creados con `CREATE INDEX IF NOT EXISTS`.

---

## 🟡 PENDIENTES A FUTURO (Mediano y largo plazo)

### Frontend & UI
- [ ] **Modularización de `index.html`:**
  - Separar los módulos grandes en componentes o migrar a Vue 3 / Vite.
- [ ] **Revisión profunda de `innerHTML`:**
  - Continuar asegurando que todas las variables dinámicas pasen por `escapeHTML()` antes de inyectarse.

### Dependencias
- [ ] **Monitorear xhtml2pdf:**
  - Actualizar cuando el mantenedor publique versión con aviso de seguridad corregido.
