-- ═══════════════════════════════════════════════════════════════════════════
-- ESQUEMA COMPLETO PARA SUPABASE (POSTGRESQL) — COMUNA PRODUCTIVA PRESIDENTE OBRERO
-- Código Comunal: C-MIX-2018-11-0019
-- ═══════════════════════════════════════════════════════════════════════════

-- Habilitar extensión UUID si se requiere
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Consejos Comunales
CREATE TABLE IF NOT EXISTS consejos_comunales (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    rif TEXT,
    sector TEXT,
    fecha_constitucion TEXT,
    vocero_coordinador TEXT,
    telefono TEXT,
    email TEXT,
    poblacion_total INTEGER DEFAULT 0,
    activo INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Voceros
CREATE TABLE IF NOT EXISTS voceros (
    id SERIAL PRIMARY KEY,
    consejo_id INTEGER REFERENCES consejos_comunales(id) ON DELETE SET NULL,
    nombre TEXT NOT NULL,
    cedula TEXT,
    cargo TEXT NOT NULL,
    telefono TEXT,
    email TEXT,
    tipo TEXT DEFAULT 'Principal',
    votos INTEGER DEFAULT 0,
    activo INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Instancias de Gobierno (Art. 28 LOC)
CREATE TABLE IF NOT EXISTS instancias_gobierno (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL,
    descripcion TEXT,
    base_legal TEXT,
    fecha_constitucion TEXT,
    activa INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Instancias Voceros (Puente)
CREATE TABLE IF NOT EXISTS instancias_voceros (
    id SERIAL PRIMARY KEY,
    instancia_id INTEGER REFERENCES instancias_gobierno(id) ON DELETE CASCADE,
    vocero_id INTEGER REFERENCES voceros(id) ON DELETE CASCADE,
    cargo_instancia TEXT NOT NULL,
    fecha_designacion TEXT,
    activo INTEGER DEFAULT 1,
    UNIQUE(instancia_id, vocero_id)
);

-- 5. Comisiones de Gestión Comunal (Art. 30 LOC)
CREATE TABLE IF NOT EXISTS comisiones_gestion (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    area_tematica TEXT,
    descripcion TEXT,
    responsable_id INTEGER REFERENCES voceros(id) ON DELETE SET NULL,
    activa INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. Vocerías
CREATE TABLE IF NOT EXISTS vocerias (
    id SERIAL PRIMARY KEY,
    vocero_id INTEGER REFERENCES voceros(id) ON DELETE CASCADE,
    tipo_asignacion TEXT NOT NULL,
    instancia_id INTEGER REFERENCES instancias_gobierno(id) ON DELETE CASCADE,
    comision_id INTEGER REFERENCES comisiones_gestion(id) ON DELETE CASCADE,
    cargo TEXT NOT NULL,
    fecha_inicio TEXT,
    fecha_fin TEXT,
    activa INTEGER DEFAULT 1
);

-- 7. Censo Maestro (Familias)
CREATE TABLE IF NOT EXISTS censo (
    id SERIAL PRIMARY KEY,
    consejo_id INTEGER REFERENCES consejos_comunales(id) ON DELETE CASCADE,
    familia_codigo TEXT UNIQUE,
    jefe_familia TEXT NOT NULL,
    cedula_jefe TEXT,
    direccion TEXT,
    telefono TEXT,
    fecha_registro TEXT DEFAULT CURRENT_DATE::text,
    activo INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 8. Censo Demográfico
CREATE TABLE IF NOT EXISTS censo_demografico (
    id SERIAL PRIMARY KEY,
    censo_id INTEGER REFERENCES censo(id) ON DELETE CASCADE,
    nombre_completo TEXT NOT NULL,
    cedula TEXT,
    fecha_nacimiento TEXT,
    sexo TEXT,
    parentesco TEXT,
    nivel_educativo TEXT,
    ocupacion TEXT,
    ingreso_mensual NUMERIC DEFAULT 0
);

-- 9. Censo Discapacidad
CREATE TABLE IF NOT EXISTS censo_discapacidad (
    id SERIAL PRIMARY KEY,
    demografico_id INTEGER REFERENCES censo_demografico(id) ON DELETE CASCADE,
    tipo_discapacidad TEXT NOT NULL,
    grado TEXT,
    certificado_conapdis INTEGER DEFAULT 0,
    observaciones TEXT
);

-- 10. Censo Viviendas
CREATE TABLE IF NOT EXISTS censo_viviendas (
    id SERIAL PRIMARY KEY,
    censo_id INTEGER REFERENCES censo(id) ON DELETE CASCADE,
    tipo_vivienda TEXT,
    tenencia TEXT,
    material_paredes TEXT,
    material_techo TEXT,
    material_piso TEXT,
    num_habitaciones INTEGER DEFAULT 1,
    num_banos INTEGER DEFAULT 1,
    estado_general TEXT
);

-- 11. Censo Servicios Públicos
CREATE TABLE IF NOT EXISTS censo_servicios_publicos (
    id SERIAL PRIMARY KEY,
    vivienda_id INTEGER REFERENCES censo_viviendas(id) ON DELETE CASCADE,
    servicio TEXT NOT NULL,
    tiene INTEGER DEFAULT 0,
    calidad TEXT,
    frecuencia TEXT,
    observaciones TEXT
);

-- 12. Censo Electoral Comunal
CREATE TABLE IF NOT EXISTS censo_electoral (
    id SERIAL PRIMARY KEY,
    consejo_id INTEGER REFERENCES consejos_comunales(id) ON DELETE CASCADE,
    cedula TEXT NOT NULL,
    nombre TEXT NOT NULL,
    fecha_nacimiento TEXT,
    direccion TEXT,
    centro_votacion TEXT,
    mesa INTEGER DEFAULT 1,
    habilitado INTEGER DEFAULT 1,
    fecha_actualizacion TEXT DEFAULT CURRENT_DATE::text
);

-- 13. Rendición de Cuentas (Art. 52 LOC)
CREATE TABLE IF NOT EXISTS rendiciones_cuentas (
    id SERIAL PRIMARY KEY,
    periodo TEXT NOT NULL,
    instancia_id INTEGER REFERENCES instancias_gobierno(id) ON DELETE SET NULL,
    comision_id INTEGER REFERENCES comisiones_gestion(id) ON DELETE SET NULL,
    tipo TEXT NOT NULL DEFAULT 'Ordinaria',
    fecha_rendicion TEXT NOT NULL,
    presupuesto_asignado NUMERIC DEFAULT 0,
    presupuesto_ejecutado NUMERIC DEFAULT 0,
    descripcion_logros TEXT,
    observaciones TEXT,
    aprobada INTEGER DEFAULT 0,
    acta_pdf_path TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 14. Gaceta Comunal (Art. 41 LOC)
CREATE TABLE IF NOT EXISTS gaceta_comunal (
    id SERIAL PRIMARY KEY,
    numero TEXT UNIQUE NOT NULL,
    fecha TEXT NOT NULL,
    titulo TEXT NOT NULL,
    tipo_decision TEXT NOT NULL,
    contenido TEXT NOT NULL,
    parlamento_sesion TEXT,
    aprobado_por TEXT,
    pdf_path TEXT,
    publicada INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 15. Proyectos ACA (Agenda Concreta de Acción)
CREATE TABLE IF NOT EXISTS proyectos_aca (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    codigo_proyecto TEXT UNIQUE,
    descripcion TEXT,
    comision_id INTEGER REFERENCES comisiones_gestion(id) ON DELETE SET NULL,
    consejo_id INTEGER REFERENCES consejos_comunales(id) ON DELETE SET NULL,
    monto_estimado NUMERIC DEFAULT 0,
    monto_ejecutado NUMERIC DEFAULT 0,
    fecha_inicio TEXT,
    fecha_fin_estimada TEXT,
    estado TEXT DEFAULT 'planificado',
    porcentaje_avance INTEGER DEFAULT 0,
    beneficiarios INTEGER DEFAULT 0,
    observaciones TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Habilitar Row Level Security (RLS) básico
ALTER TABLE consejos_comunales ENABLE ROW LEVEL SECURITY;
ALTER TABLE voceros ENABLE ROW LEVEL SECURITY;
ALTER TABLE instancias_gobierno ENABLE ROW LEVEL SECURITY;
ALTER TABLE comisiones_gestion ENABLE ROW LEVEL SECURITY;
ALTER TABLE gaceta_comunal ENABLE ROW LEVEL SECURITY;
ALTER TABLE proyectos_aca ENABLE ROW LEVEL SECURITY;

-- Políticas de lectura pública para la Comuna
CREATE POLICY "Lectura pública comunal" ON consejos_comunales FOR SELECT USING (true);
CREATE POLICY "Lectura voceros pública" ON voceros FOR SELECT USING (true);
CREATE POLICY "Lectura instancias pública" ON instancias_gobierno FOR SELECT USING (true);
CREATE POLICY "Lectura comisiones pública" ON comisiones_gestion FOR SELECT USING (true);
CREATE POLICY "Lectura gaceta pública" ON gaceta_comunal FOR SELECT USING (true);
CREATE POLICY "Lectura proyectos pública" ON proyectos_aca FOR SELECT USING (true);

