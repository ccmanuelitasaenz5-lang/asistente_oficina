# 📋 TAREAS PENDIENTES — Mejoras Asistente Comunal CPPO
**Creado:** 19 de julio de 2026  
**Estado:** ⏳ Pendiente para próxima sesión  
**Basado en:** Auditorías Backend, Frontend y Análisis Crítico del Agente IA (24 archivos)

---

## 🔴 URGENTE — Hacer primero (< 2h de trabajo total)

### Backend
- [x] **1. Mover datos personales hardcodeados a `.env`** (`backend/letters.py`)
- [x] **2. Corregir OCR síncrono que bloquea el event loop** (`backend/pdf_extractor.py`)
- [x] **3. Eliminar los 10 `logging.basicConfig` duplicados** (crear `logging_config.py`)

### Frontend
- [x] **4. Eliminar archivo huérfano `app.js`**
- [x] **5. Agregar `integrity` (SRI) a los recursos CDN** (`index.html`)

---

## 🟡 IMPORTANTE — Próximas 2 semanas

### Backend & Lógica
- [x] **6. Optimizar RAG y Reducir Costos de IA (Fase 1 de 3 completada)**
  - Archivo: `backend/universal_agent.py`
  - ✅ **Fase 1 completada** (29/09/2026):
    - Contexto limitado a máximo 30 entradas (antes: 60 para voceros, 15 para otros)
    - Resúmenes compactos por tipo de fuente, con cédula incluida
    - SQL con parámetros seguros (sin f-strings con valores de usuario)
    - Función `_truncar` definida una sola vez (no dentro del bucle)
    - Parámetro `formato` eliminado de `_generar_respuesta_ia`
    - Prueba funcional exitosa: 30 voceros, 8.6 segundos
  - ⏳ **Fase 2 pendiente**: Cache LRU con TTL de 5 min + timeouts por fuente (5s)
  - ⏳ **Fase 3 pendiente**: Paralelismo con timeout individual + FTS
### Frontend
- [ ] **12. Mitigar riesgo XSS (35 usos de `innerHTML`)** (`frontend/index.html`)
- [ ] **13. Separar código del `index.html` (Monolito de 3.323 líneas)**

---

## 🔵 CUANDO SALGA A INTERNET — Antes del despliegue

- [ ] **14. Hacer `API_KEY` obligatoria en producción**
- [ ] **15. Proteger archivos estáticos `/media`, `/cartas`, `/informes`**
- [ ] **16. Agregar rate limiting con `slowapi`**
- [ ] **17. Sanitizar SQL injection en LanceDB**
- [ ] **18. Configurar CSP en el backend para el frontend**

---

## 🧠 EVOLUCIÓN DEL AGENTE IA (De Chatbot a Asistente Ejecutor)

- [x] **19. Agente Ejecutor (Function Calling)**
  - Acción: Dotar al agente de herramientas para que *haga cosas*, no solo responda (ej: `programar_actividad()`, `generar_carta()`, `crear_vocero()`).
- [ ] **20. Manejo de Errores IA y Retry**
  - Acción: Implementar backoff exponencial si fallan los proveedores.
- [ ] **21. Modo Asistente Proactivo**
  - Acción: Alertas automáticas (cargos vencidos, falta de actividades, recordatorios de consultas).
- [ ] **22. Feedback Loop**
  - Acción: Botón 👍/👎 en frontend para guardar respuestas fallidas y afinar prompts.

---

## 📦 MEJORAS A MÓDULOS DE NEGOCIO (Mediano plazo)

- **Calendario**: Sincronización bidireccional, agenda pública, alertas por WhatsApp/SMS.
- **Reportes**: Reportes automáticos mensuales, formatos institucionales (CNE, MinComunas).
- **Cartas**: Numeración correlativa automática, plantillas parametrizables, registro de respuestas.
- **Actas**: Firma digital, cálculo de quórum automático.
- **Actividades**: Control de asistencia, carga múltiple de fotos, presupuesto.
- **Consultas**: Voto ponderado, resultados en tiempo real, cierre automático.

---

## 🟣 REFACTORIZACIÓN MAYOR (A mediano/largo plazo)

- [ ] **23. Migrar Frontend a Vue 3 + Vite**
- [ ] **24. Separar `main.py` en routers organizados (Backend)**
- [ ] **25. Implementar patrón Repository/Service (Backend)**

---

## ❓ DECISIONES PENDIENTES (Actualizado)

1. ¿Mover datos personales de `letters.py` a `.env`?
2. ¿Mantener SQLite o migrar a PostgreSQL? *(Recomendación: quedarse con SQLite)*
3. ¿Autenticación por usuarios (login) o solo API key?
4. ¿Para el frontend prefieres Vue 3 o React? *(Recomendación: Vue 3)*
5. **¿Empezamos transformando el Agente a "Agente Ejecutor" o resolvemos primero la seguridad básica?**
6. ¿Despliegue en servidor/VPS o Docker local por ahora?
