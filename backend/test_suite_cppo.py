"""
test_suite_cppo.py
Suite de pruebas integrales para el Asistente Comunal CPPO.
Verifica:
1. Base de datos e integridad del esquema v3.
2. Endpoints de Instancias de Gobierno.
3. Endpoints de Comisiones de Gestión.
4. Endpoints del Censo Comunal (Familias, Miembros, Vivienda, Servicios, Estadísticas, Electoral).
5. Endpoints de Rendición de Cuentas (Art. 52 LOC).
6. Endpoints de Gaceta Comunal (Art. 41 LOC y generación de PDF).
7. Endpoints de Proyectos ACA (Agenda Concreta de Acción).
8. Agente Universal de IA y consultas a la LOC.
9. PWA (Manifest y Service Worker).
"""

import sys
import asyncio
import json
from datetime import datetime
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.database import get_db
from backend.loc_knowledge import buscar_articulos_loc
from backend.universal_agent import _clasificar_intencion, _buscar_instancias, _buscar_censo, _buscar_gaceta, _buscar_loc


class TestReport:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []

    def log(self, category: str, name: str, success: bool, details: str = ""):
        status = "PASSED" if success else "FAILED"
        if success:
            self.passed += 1
            print(f"  [OK] {category} -> {name}")
        else:
            self.failed += 1
            print(f"  [XX] {category} -> {name}: {details}")
        self.results.append({
            "category": category,
            "name": name,
            "status": status,
            "details": details
        })


async def run_all_tests():
    report = TestReport()
    print("=" * 70)
    print("INICIANDO SUITE DE PRUEBAS: ASISTENTE COMUNAL CPPO")
    print(f"Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # ─────────────────────────────────────────────────────────────────────────
    # 1. BASE DE DATOS Y ESQUEMA V3
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- 1. Pruebas de Base de Datos y Esquema v3 ---")
    async with await get_db() as db:
        # Verificar version
        cursor = await db.execute("SELECT MAX(version) FROM schema_version")
        ver = (await cursor.fetchone())[0]
        report.log("Base de Datos", "Schema Version 3 aplicada", ver >= 3, f"Version encontrada: {ver}")

        # Verificar tablas esperadas
        cur_tables = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in await cur_tables.fetchall()]
        tablas_requeridas = [
            'instancias_gobierno', 'instancias_voceros', 'comisiones_gestion',
            'vocerias', 'censo', 'censo_demografico', 'censo_discapacidad',
            'censo_viviendas', 'censo_servicios_publicos', 'censo_servicios_basicos',
            'censo_electoral', 'rendiciones_cuentas', 'gaceta_comunal', 'proyectos_aca'
        ]
        for t in tablas_requeridas:
            report.log("Base de Datos", f"Tabla '{t}' existente", t in tables)

        # Verificar seeds
        cur_inst = await db.execute("SELECT COUNT(*) FROM instancias_gobierno")
        inst_count = (await cur_inst.fetchone())[0]
        report.log("Base de Datos", "Semillas Instancias de Gobierno (>= 5)", inst_count >= 5, f"Cantidad: {inst_count}")

        cur_com = await db.execute("SELECT COUNT(*) FROM comisiones_gestion")
        com_count = (await cur_com.fetchone())[0]
        report.log("Base de Datos", "Semillas Comisiones de Gestión (>= 6)", com_count >= 6, f"Cantidad: {com_count}")

        # Obtener un consejo comunal y un vocero para los tests posteriores
        cur_cc = await db.execute("SELECT id FROM consejos_comunales LIMIT 1")
        row_cc = await cur_cc.fetchone()
        if not row_cc:
            await db.execute("INSERT INTO consejos_comunales (nombre, sector) VALUES ('CC Central Prueba', 'Sector Central')")
            await db.commit()
            cur_cc = await db.execute("SELECT id FROM consejos_comunales LIMIT 1")
            row_cc = await cur_cc.fetchone()
        test_consejo_id = row_cc[0]

        cur_voc = await db.execute("SELECT id FROM voceros LIMIT 1")
        row_voc = await cur_voc.fetchone()
        if not row_voc:
            await db.execute("INSERT INTO voceros (consejo_id, nombre, cedula, cargo) VALUES (?, 'Vocero de Prueba', 'V-99999999', 'Vocero Principal')", (test_consejo_id,))
            await db.commit()
            cur_voc = await db.execute("SELECT id FROM voceros LIMIT 1")
            row_voc = await cur_voc.fetchone()
        test_vocero_id = row_voc[0]

    # ─────────────────────────────────────────────────────────────────────────
    # 2. PRUEBAS HTTP CON ASGI TEST CLIENT
    # ─────────────────────────────────────────────────────────────────────────
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # ── 2.1 Instancias de Gobierno ──────────────────────────────
        print("\n--- 2. Pruebas de API: Instancias de Gobierno ---")
        res = await client.get("/api/instancias")
        report.log("API Instancias", "GET /api/instancias (200 OK)", res.status_code == 200)
        instancias_data = res.json()
        report.log("API Instancias", "Lista de instancias contiene elementos", len(instancias_data) >= 5)

        test_instancia_id = instancias_data[0]["id"] if instancias_data else 1

        # Asignar vocero a instancia
        payload_asig = {
            "vocero_id": test_vocero_id,
            "cargo_instancia": "Coordinador de Prueba",
            "fecha_designacion": "2026-10-29"
        }
        res_asig = await client.post(f"/api/instancias/{test_instancia_id}/voceros", json=payload_asig)
        report.log("API Instancias", "POST /api/instancias/{id}/voceros (200 OK)", res_asig.status_code == 200, res_asig.text)

        # Detalle de instancia con voceros
        res_det = await client.get(f"/api/instancias/{test_instancia_id}")
        det_data = res_det.json()
        tiene_vocero = any(v["vocero_id"] == test_vocero_id for v in det_data.get("voceros", []))
        report.log("API Instancias", "Vocero asignado reflejado en detalle de instancia", tiene_vocero)

        # ── 2.2 Comisiones de Gestión ──────────────────────────────
        print("\n--- 3. Pruebas de API: Comisiones de Gestión ---")
        res_com = await client.get("/api/comisiones")
        report.log("API Comisiones", "GET /api/comisiones (200 OK)", res_com.status_code == 200)
        comisiones_data = res_com.json()
        report.log("API Comisiones", "Comisiones temáticas iniciales cargadas", len(comisiones_data) >= 6)

        # Crear nueva comisión
        payload_com = {
            "nombre": f"Comisión de Innovación Comunal {datetime.now().strftime('%M%S')}",
            "area_tematica": "Tecnología e Innovación",
            "descripcion": "Comisión especial para desarrollo técnico y científico comunal."
        }
        res_create_com = await client.post("/api/comisiones", json=payload_com)
        report.log("API Comisiones", "POST /api/comisiones (200 OK)", res_create_com.status_code == 200, res_create_com.text)
        nueva_com_id = res_create_com.json().get("id")

        # Asignar vocero a comisión
        res_asig_com = await client.post(f"/api/comisiones/{nueva_com_id}/voceros", json={
            "vocero_id": test_vocero_id,
            "cargo": "Enlace Tecnológico"
        })
        report.log("API Comisiones", "POST /api/comisiones/{id}/voceros (200 OK)", res_asig_com.status_code == 200)

        # ── 2.3 Censo Comunal ──────────────────────────────────────
        print("\n--- 4. Pruebas de API: Censo Comunal y Padrón Electoral ---")
        payload_familia = {
            "consejo_id": test_consejo_id,
            "jefe_familia": "Familia de Prueba Integrada",
            "cedula_jefe": f"V-{datetime.now().strftime('%H%M%S')}",
            "direccion": "Calle Real, Sector Central, Casa 10",
            "telefono": "0412-1234567",
            "miembros": [
                {
                    "nombre_completo": "Familia de Prueba Integrada",
                    "cedula": f"V-{datetime.now().strftime('%H%M%S')}",
                    "parentesco": "Jefe de Familia",
                    "sexo": "F",
                    "ocupacion": "Docente Comunal",
                    "discapacidad": {
                        "tipo_discapacidad": "Visual",
                        "grado": "Moderada",
                        "certificado_conapdis": 1,
                        "observaciones": "Uso de lentes correctivos especiales"
                    }
                },
                {
                    "nombre_completo": "Hijo de Prueba",
                    "parentesco": "Hijo",
                    "sexo": "M",
                    "fecha_nacimiento": "2015-05-10"
                }
            ],
            "vivienda": {
                "tipo_vivienda": "Casa",
                "tenencia": "Propia",
                "material_paredes": "Bloque",
                "material_techo": "Platabanda",
                "estado_general": "Bueno"
            },
            "servicios": [
                {"servicio": "Agua potable", "tiene": 1, "frecuencia": "Continuo"},
                {"servicio": "Electricidad", "tiene": 1, "frecuencia": "Continuo"},
                {"servicio": "Gas Comunal", "tiene": 1, "frecuencia": "Mensual"}
            ]
        }
        res_fam = await client.post("/api/censo/familias", json=payload_familia)
        report.log("API Censo", "POST /api/censo/familias (200 OK)", res_fam.status_code == 200, res_fam.text)
        censo_id = res_fam.json().get("censo_id")

        # Detalle de familia
        res_fam_det = await client.get(f"/api/censo/familias/{censo_id}")
        det_fam_data = res_fam_det.json()
        report.log("API Censo", "Expediente familiar recupera miembros y discapacidad", 
                   len(det_fam_data.get("miembros", [])) == 2 and det_fam_data["miembros"][0].get("tipo_discapacidad") == "Visual")
        report.log("API Censo", "Expediente familiar recupera vivienda y servicios", 
                   det_fam_data.get("vivienda") is not None and len(det_fam_data["vivienda"].get("servicios", [])) == 3)

        # Estadísticas censales
        res_stats = await client.get("/api/censo/estadisticas")
        stats_data = res_stats.json()
        report.log("API Censo", "GET /api/censo/estadisticas calcula métricas", 
                   stats_data.get("total_familias", 0) >= 1 and stats_data.get("total_discapacitados", 0) >= 1)

        # Censo Electoral
        payload_elector = {
            "consejo_id": test_consejo_id,
            "nombre": "Elector Comunal Verificado",
            "cedula": f"V-88{datetime.now().strftime('%M%S')}",
            "mesa": 1,
            "habilitado": 1
        }
        res_elector = await client.post("/api/censo/electoral", json=payload_elector)
        report.log("API Censo", "POST /api/censo/electoral (200 OK)", res_elector.status_code == 200)

        res_electores = await client.get("/api/censo/electoral")
        report.log("API Censo", "GET /api/censo/electoral lista electores", res_electores.json().get("total", 0) >= 1)

        # ── 2.4 Rendición de Cuentas ──────────────────────────────
        print("\n--- 5. Pruebas de API: Rendición de Cuentas (Art. 52 LOC) ---")
        payload_rend = {
            "periodo": "2026-Q3",
            "instancia_id": test_instancia_id,
            "tipo": "Ordinaria",
            "fecha_rendicion": "2026-10-29",
            "presupuesto_asignado": 150000.0,
            "presupuesto_ejecutado": 142500.0,
            "descripcion_logros": "Ejecución completa del plan de mantenimiento eléctrico y dotación comunal.",
            "aprobada": 0
        }
        res_rend = await client.post("/api/rendiciones", json=payload_rend)
        report.log("API Rendiciones", "POST /api/rendiciones (200 OK)", res_rend.status_code == 200)
        rend_id = res_rend.json().get("id")

        # Balance presupuestario
        res_resumen = await client.get("/api/rendiciones/resumen")
        resumen_data = res_resumen.json()
        report.log("API Rendiciones", "GET /api/rendiciones/resumen calcula totales financieros",
                   resumen_data.get("total_asignado", 0) >= 150000.0)

        # Aprobación de rendición
        res_aprob = await client.post(f"/api/rendiciones/{rend_id}/aprobar", json={
            "aprobada": 1,
            "observaciones": "Aprobada por unanimidad en sesión ordinaria del Parlamento Comunal."
        })
        report.log("API Rendiciones", "POST /api/rendiciones/{id}/aprobar (200 OK)", res_aprob.status_code == 200)

        # ── 2.5 Gaceta Comunal ─────────────────────────────────────
        print("\n--- 6. Pruebas de API: Gaceta Comunal (Art. 41 LOC) ---")
        res_corr = await client.get("/api/gaceta/siguiente-numero")
        num_sugerido = res_corr.json().get("numero")
        report.log("API Gaceta", "Generación de correlativo continuo (GC-CPPO-YYYY-NNNN)", 
                   num_sugerido is not None and "GC-CPPO-" in num_sugerido)

        payload_gaceta = {
            "numero": num_sugerido,
            "fecha": "2026-10-29",
            "titulo": "Acuerdo Comunal de Protección del Hábitat y la Cuenca Hidrográfica",
            "tipo_decision": "Acuerdo Comunal",
            "contenido": "EL PARLAMENTO COMUNAL DE LA COMUNA PRODUCTIVA PRESIDENTE OBRERO SANCIONA EL PRESENTE ACUERDO...",
            "parlamento_sesion": "Sesión Ordinaria N° 15",
            "aprobado_por": "Parlamento Comunal en Pleno"
        }
        res_gaceta = await client.post("/api/gaceta", json=payload_gaceta)
        report.log("API Gaceta", "POST /api/gaceta (200 OK)", res_gaceta.status_code == 200)
        gaceta_id = res_gaceta.json().get("id")

        # Generar PDF de la gaceta
        res_pdf = await client.get(f"/api/gaceta/{gaceta_id}/pdf")
        report.log("API Gaceta", "GET /api/gaceta/{id}/pdf genera documento oficial PDF", 
                   res_pdf.status_code == 200 and "pdf_url" in res_pdf.json())

        # ── 2.6 Proyectos ACA ──────────────────────────────────────
        print("\n--- 7. Pruebas de API: Agenda Concreta de Acción (ACA) ---")
        payload_proy = {
            "nombre": "Rehabilitación de Alumbrado Público Sector Suramérica",
            "comision_id": nueva_com_id,
            "consejo_id": test_consejo_id,
            "monto_estimado": 85000.0,
            "beneficiarios": 320,
            "descripcion": "Instalación de 40 luminarias LED solares de alta eficiencia."
        }
        res_proy = await client.post("/api/proyectos", json=payload_proy)
        report.log("API Proyectos", "POST /api/proyectos (200 OK)", res_proy.status_code == 200)
        proy_id = res_proy.json().get("id")

        # Actualizar avance
        res_avance = await client.put(f"/api/proyectos/{proy_id}/avance", json={
            "porcentaje_avance": 75,
            "monto_ejecutado": 63750.0,
            "observaciones": "75% de las luminarias instaladas satisfactoriamente."
        })
        report.log("API Proyectos", "PUT /api/proyectos/{id}/avance actualiza progreso", res_avance.status_code == 200)

        # Dashboard de proyectos
        res_dash_p = await client.get("/api/proyectos/dashboard")
        dash_p_data = res_dash_p.json()
        report.log("API Proyectos", "GET /api/proyectos/dashboard calcula métricas de inversión",
                   dash_p_data.get("total_proyectos", 0) >= 1 and dash_p_data.get("inversion_total_estimada", 0) >= 85000.0)

    # ─────────────────────────────────────────────────────────────────────────
    # 3. AGENTE DE IA Y CONOCIMIENTO LEGAL (LOC)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- 8. Pruebas de IA y Base Jurídica (LOC) ---")
    # Prueba del clasificador de intención
    intenciones = _clasificar_intencion("¿Quiénes son los voceros de las instancias de gobierno y qué dice el artículo 28 de la LOC?")
    report.log("Agente IA", "Clasificador detecta intención 'instancias'", "instancias" in intenciones)
    report.log("Agente IA", "Clasificador detecta intención 'legal'", "legal" in intenciones)

    # Búsqueda legal en la LOC
    arts_loc = buscar_articulos_loc("artículo 28")
    report.log("Conocimiento LOC", "Búsqueda directa Art. 28 LOC", len(arts_loc) == 1 and arts_loc[0]["numero"] == 28)

    arts_loc_tematica = buscar_articulos_loc("rendición de cuentas de los voceros")
    report.log("Conocimiento LOC", "Búsqueda temática LOC (encuentra Art. 52)", any(a["numero"] == 52 for a in arts_loc_tematica))

    # Búsqueda en instancias
    res_b_inst = await _buscar_instancias("contraloría")
    report.log("Agente IA", "Búsqueda universal en tabla 'instancias_gobierno'", len(res_b_inst) >= 1)

    # Búsqueda en censo
    res_b_censo = await _buscar_censo("Prueba")
    report.log("Agente IA", "Búsqueda universal en tabla 'censo'", len(res_b_censo) >= 1)

    # Búsqueda en gaceta
    res_b_gac = await _buscar_gaceta("Acuerdo")
    report.log("Agente IA", "Búsqueda universal en tabla 'gaceta_comunal'", len(res_b_gac) >= 1)

    # ─────────────────────────────────────────────────────────────────────────
    # 4. PWA Y ARCHIVOS ESTÁTICOS
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- 9. Pruebas de PWA y Archivos Estáticos ---")
    manifest_file = Path("frontend/manifest.json")
    report.log("PWA", "Archivo manifest.json existe", manifest_file.exists())
    if manifest_file.exists():
        manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
        report.log("PWA", "Manifest contiene display standalone y theme_color", 
                   manifest_data.get("display") == "standalone" and "theme_color" in manifest_data)

    sw_file = Path("frontend/sw.js")
    report.log("PWA", "Service Worker sw.js existe", sw_file.exists())
    if sw_file.exists():
        sw_text = sw_file.read_text(encoding="utf-8")
        report.log("PWA", "Service Worker maneja eventos 'fetch' y 'push'", 
                   "'fetch'" in sw_text and "'push'" in sw_text)

    modules_file = Path("frontend/comuna_modules.js")
    report.log("Frontend", "Archivo comuna_modules.js existe", modules_file.exists())
    if modules_file.exists():
        mod_text = modules_file.read_text(encoding="utf-8")
        report.log("Frontend", "Funciones clave de autogobierno definidas en JS",
                   "loadInstancias" in mod_text and "loadCenso" in mod_text and "loadGaceta" in mod_text and "loadProyectos" in mod_text)

    # ─────────────────────────────────────────────────────────────────────────
    # RESUMEN FINAL
    # ─────────────────────────────────────────────────────────────────────────
    total = report.passed + report.failed
    tasa = (report.passed / total * 100) if total > 0 else 0
    print("\n" + "=" * 70)
    print("RESUMEN DE PRUEBAS DEL ASISTENTE COMUNAL CPPO")
    print(f"Total pruebas ejecutadas: {total}")
    print(f"Pruebas superadas (PASS): {report.passed}")
    print(f"Pruebas fallidas (FAIL):  {report.failed}")
    print(f"Tasa de éxito:            {tasa:.1f}%")
    print("=" * 70)

    if report.failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(run_all_tests())

