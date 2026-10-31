"""
Migración v3: Expansión de Consejos Comunales a Gestión de Comuna Completa.
Incluye instancias de gobierno, comisiones de gestión, vocerías, censo comunal
(maestro, demográfico, discapacidad, vivienda, servicios públicos, servicios básicos, electoral),
rendición de cuentas, gaceta comunal y proyectos ACA.
"""

import logging

logger = logging.getLogger("migrations.v3_comuna")

INSTANCIAS_DEFAULT = [
    ("Comisión Electoral Permanente", "Electoral", "Instancia encargada de coordinar y organizar los procesos electorales y consultas populares en el territorio comunal.", "Art. 36 LOC"),
    ("Consejo de Contraloría Comunal", "Contraloría", "Instancia encargada de la vigilancia, control, seguimiento y evaluación social de la gestión comunal.", "Art. 37 LOC"),
    ("Banco de la Comuna", "Banco", "Instancia económica-financiera encargada de la administración de recursos y el financiamiento de proyectos comunales.", "Art. 38 LOC"),
    ("Parlamento Comunal", "Parlamento", "Máxima instancia del autogobierno comunal para la deliberación, decisiones y aprobación de normativas.", "Art. 21 LOC"),
    ("Consejo de Justicia de Paz Comunal", "Justicia", "Instancia encargada de prevenir y solucionar conflictos comunitarios mediante la conciliación.", "Art. 54 LOC"),
]

COMISIONES_DEFAULT = [
    ("Salud", "Área social y preventiva para la atención médica comunitaria."),
    ("Educación", "Formación sociopolítica, cultural y programas educativos comunales."),
    ("Tierras Urbanas", "Regularización de la tenencia de la tierra y ordenamiento comunal."),
    ("Hábitat y Vivienda", "Planificación, rehabilitación y construcción de viviendas y servicios conexos."),
    ("Economía Comunal", "Desarrollo de encadenamientos productivos y empresas de propiedad social directa comunal."),
    ("Seguridad y Defensa", "Prevención, convivencia ciudadana y defensa integral de la comunidad."),
]


async def aplicar_migracion_v3(db):
    """Ejecuta la migración v3 sobre la base de datos aiosqlite activa."""
    logger.info("Iniciando aplicación de Migración v3: Gestión Comunal Completa...")

    # 1. Modificación a consejos_comunales: agregar poblacion_total
    try:
        await db.execute("ALTER TABLE consejos_comunales ADD COLUMN poblacion_total INTEGER DEFAULT 0;")
        logger.info("Columna poblacion_total agregada a consejos_comunales.")
    except Exception:
        # Ya existe la columna
        pass

    # 2. Instancias de Gobierno (Art. 28 LOC)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS instancias_gobierno (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        tipo TEXT NOT NULL,
        descripcion TEXT,
        base_legal TEXT,
        fecha_constitucion TEXT,
        activa INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. Comisiones de Gestión Comunal (Art. 30 LOC)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS comisiones_gestion (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        area_tematica TEXT,
        descripcion TEXT,
        responsable_id INTEGER,
        activa INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (responsable_id) REFERENCES voceros(id)
    );
    """)

    # 4. Tabla puente: Instancias - Voceros
    await db.execute("""
    CREATE TABLE IF NOT EXISTS instancias_voceros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instancia_id INTEGER NOT NULL,
        vocero_id INTEGER NOT NULL,
        cargo_instancia TEXT NOT NULL,
        fecha_designacion TEXT,
        activo INTEGER DEFAULT 1,
        FOREIGN KEY (instancia_id) REFERENCES instancias_gobierno(id),
        FOREIGN KEY (vocero_id) REFERENCES voceros(id),
        UNIQUE(instancia_id, vocero_id)
    );
    """)

    # 5. Vocerías (detalle y asignaciones a instancias/comisiones)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS vocerias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vocero_id INTEGER NOT NULL,
        tipo_asignacion TEXT NOT NULL,     -- 'instancia' o 'comision'
        instancia_id INTEGER,
        comision_id INTEGER,
        cargo TEXT NOT NULL,
        fecha_inicio TEXT,
        fecha_fin TEXT,
        activa INTEGER DEFAULT 1,
        FOREIGN KEY (vocero_id) REFERENCES voceros(id),
        FOREIGN KEY (instancia_id) REFERENCES instancias_gobierno(id),
        FOREIGN KEY (comision_id) REFERENCES comisiones_gestion(id)
    );
    """)

    # 6. Censo Maestro (Familias por Consejo Comunal)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS censo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        consejo_id INTEGER NOT NULL,
        familia_codigo TEXT UNIQUE,
        jefe_familia TEXT NOT NULL,
        cedula_jefe TEXT,
        direccion TEXT,
        telefono TEXT,
        fecha_registro TEXT DEFAULT (date('now')),
        activo INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (consejo_id) REFERENCES consejos_comunales(id)
    );
    """)

    # 7. Censo Demográfico (Miembros del núcleo familiar)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS censo_demografico (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        censo_id INTEGER NOT NULL,
        nombre_completo TEXT NOT NULL,
        cedula TEXT,
        fecha_nacimiento TEXT,
        sexo TEXT,
        parentesco TEXT,
        nivel_educativo TEXT,
        ocupacion TEXT,
        ingreso_mensual REAL DEFAULT 0,
        FOREIGN KEY (censo_id) REFERENCES censo(id) ON DELETE CASCADE
    );
    """)

    # 8. Censo Discapacidad
    await db.execute("""
    CREATE TABLE IF NOT EXISTS censo_discapacidad (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        demografico_id INTEGER NOT NULL,
        tipo_discapacidad TEXT NOT NULL,
        grado TEXT,
        certificado_conapdis INTEGER DEFAULT 0,
        observaciones TEXT,
        FOREIGN KEY (demografico_id) REFERENCES censo_demografico(id) ON DELETE CASCADE
    );
    """)

    # 9. Censo Viviendas
    await db.execute("""
    CREATE TABLE IF NOT EXISTS censo_viviendas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        censo_id INTEGER NOT NULL,
        tipo_vivienda TEXT,
        tenencia TEXT,
        material_paredes TEXT,
        material_techo TEXT,
        material_piso TEXT,
        num_habitaciones INTEGER DEFAULT 1,
        num_banos INTEGER DEFAULT 1,
        estado_general TEXT,
        FOREIGN KEY (censo_id) REFERENCES censo(id) ON DELETE CASCADE
    );
    """)

    # 10. Censo Servicios Públicos por Vivienda
    await db.execute("""
    CREATE TABLE IF NOT EXISTS censo_servicios_publicos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vivienda_id INTEGER NOT NULL,
        servicio TEXT NOT NULL,
        tiene INTEGER DEFAULT 0,
        calidad TEXT,
        frecuencia TEXT,
        observaciones TEXT,
        FOREIGN KEY (vivienda_id) REFERENCES censo_viviendas(id) ON DELETE CASCADE
    );
    """)

    # 11. Censo Servicios Básicos Comunitarios por Sector / Consejo
    await db.execute("""
    CREATE TABLE IF NOT EXISTS censo_servicios_basicos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        consejo_id INTEGER NOT NULL,
        servicio TEXT NOT NULL,
        disponible INTEGER DEFAULT 0,
        ubicacion TEXT,
        distancia_km REAL,
        calidad TEXT,
        observaciones TEXT,
        FOREIGN KEY (consejo_id) REFERENCES consejos_comunales(id)
    );
    """)

    # 12. Censo Electoral Comunal
    await db.execute("""
    CREATE TABLE IF NOT EXISTS censo_electoral (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        consejo_id INTEGER NOT NULL,
        cedula TEXT NOT NULL,
        nombre TEXT NOT NULL,
        fecha_nacimiento TEXT,
        direccion TEXT,
        centro_votacion TEXT,
        mesa INTEGER,
        habilitado INTEGER DEFAULT 1,
        fecha_actualizacion TEXT DEFAULT (date('now')),
        FOREIGN KEY (consejo_id) REFERENCES consejos_comunales(id)
    );
    """)

    # 13. Rendición de Cuentas (Art. 52 LOC)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS rendiciones_cuentas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        periodo TEXT NOT NULL,
        instancia_id INTEGER,
        comision_id INTEGER,
        tipo TEXT NOT NULL,
        fecha_rendicion TEXT NOT NULL,
        presupuesto_asignado REAL DEFAULT 0,
        presupuesto_ejecutado REAL DEFAULT 0,
        descripcion_logros TEXT,
        observaciones TEXT,
        aprobada INTEGER DEFAULT 0,
        acta_pdf_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (instancia_id) REFERENCES instancias_gobierno(id),
        FOREIGN KEY (comision_id) REFERENCES comisiones_gestion(id)
    );
    """)

    # 14. Gaceta Comunal (Art. 41 LOC)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS gaceta_comunal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT UNIQUE NOT NULL,
        fecha TEXT NOT NULL,
        titulo TEXT NOT NULL,
        tipo_decision TEXT NOT NULL,
        contenido TEXT NOT NULL,
        parlamento_sesion TEXT,
        aprobado_por TEXT,
        pdf_path TEXT,
        publicada INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 15. Proyectos ACA (Agenda Concreta de Acción)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS proyectos_aca (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        codigo_proyecto TEXT UNIQUE,
        descripcion TEXT,
        comision_id INTEGER,
        consejo_id INTEGER,
        monto_estimado REAL DEFAULT 0,
        monto_ejecutado REAL DEFAULT 0,
        fecha_inicio TEXT,
        fecha_fin_estimada TEXT,
        estado TEXT DEFAULT 'planificado',
        porcentaje_avance INTEGER DEFAULT 0,
        beneficiarios INTEGER DEFAULT 0,
        observaciones TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (comision_id) REFERENCES comisiones_gestion(id),
        FOREIGN KEY (consejo_id) REFERENCES consejos_comunales(id)
    );
    """)

    # ── SEMILLAS (SEED DATA) ──────────────────────────────────────────────────
    # Instancias de gobierno por defecto
    for nombre, tipo, desc, legal in INSTANCIAS_DEFAULT:
        cursor = await db.execute("SELECT id FROM instancias_gobierno WHERE nombre = ?", (nombre,))
        if not await cursor.fetchone():
            await db.execute(
                """
                INSERT INTO instancias_gobierno (nombre, tipo, descripcion, base_legal, activa)
                VALUES (?, ?, ?, ?, 1)
                """,
                (nombre, tipo, desc, legal)
            )

    # Comisiones de gestión por defecto
    for nombre, desc in COMISIONES_DEFAULT:
        cursor = await db.execute("SELECT id FROM comisiones_gestion WHERE nombre = ?", (nombre,))
        if not await cursor.fetchone():
            await db.execute(
                """
                INSERT INTO comisiones_gestion (nombre, area_tematica, descripcion, activa)
                VALUES (?, ?, ?, 1)
                """,
                (nombre, nombre, desc)
            )

    # Registrar versión en schema_version
    await db.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (3)")
    await db.commit()
    logger.info("Migración v3 aplicada exitosamente (Tablas creadas y Seeds insertados).")

