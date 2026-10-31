/**
 * comuna_modules.js
 * Módulos de Autogobierno Comunal CPPO:
 * - Instancias de Gobierno
 * - Comisiones de Gestión
 * - Censo Comunal (Familias, Miembros, Vivienda, Discapacidad, Servicios, Electoral, Dashboard)
 * - Rendición de Cuentas (Art. 52 LOC)
 * - Gaceta Comunal (Art. 41 LOC)
 * - Proyectos ACA (Agenda Concreta de Acción)
 */

// ─────────────────────────────────────────────────────────────────────────────
// 1. INSTANCIAS DE GOBIERNO
// ─────────────────────────────────────────────────────────────────────────────

async function loadInstancias() {
    const container = document.getElementById('instancias-grid');
    if (!container) return;
    container.innerHTML = '<div class="empty-state"><div class="spinner"></div><p>Cargando instancias de gobierno...</p></div>';

    try {
        const instancias = await apiFetch('/api/instancias');
        if (!instancias.length) {
            container.innerHTML = '<div class="empty-state"><p>No se encontraron instancias de gobierno configuradas.</p></div>';
            return;
        }

        container.innerHTML = instancias.map(inst => `
            <div class="card" style="display:flex;flex-direction:column;justify-content:space-between">
                <div class="card-header" style="border-bottom:1px solid var(--border);padding-bottom:12px">
                    <div>
                        <span class="badge" style="background:var(--accent-glow);color:#60a5fa;margin-bottom:6px;display:inline-block">
                            ${escapeHTML(inst.tipo)}
                        </span>
                        <div class="card-title" style="font-size:15px;font-weight:700">
                            ${escapeHTML(inst.nombre)}
                        </div>
                        <div style="font-size:11px;color:var(--txt-muted);margin-top:2px">
                            ${escapeHTML(inst.base_legal || 'Art. LOC')}
                        </div>
                    </div>
                    <button class="btn btn-primary" onclick="abrirModalAsignarInstancia(${inst.id}, '${escapeHTML(inst.nombre)}')" style="font-size:11px;padding:5px 10px">
                        <i data-lucide="user-plus" style="width:13px;height:13px"></i>
                        <span>Asignar</span>
                    </button>
                </div>
                <div class="card-body" style="padding:14px;flex:1">
                    <p style="font-size:12px;color:var(--txt-muted);margin-bottom:12px">
                        ${escapeHTML(inst.descripcion || 'Sin descripción')}
                    </p>
                    <div style="font-size:11px;font-weight:700;color:var(--txt-faint);text-transform:uppercase;margin-bottom:8px">
                        Voceros Designados (${inst.voceros.length})
                    </div>
                    ${inst.voceros.length === 0 ? `
                        <div style="font-size:12px;color:var(--txt-muted);background:rgba(255,255,255,0.02);padding:10px;border-radius:6px;text-align:center">
                            Sin voceros miembros asignados
                        </div>
                    ` : `
                        <div style="display:flex;flex-direction:column;gap:6px;max-height:220px;overflow-y:auto">
                            ${inst.voceros.map(v => `
                                <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 8px;background:var(--bg-card-2);border-radius:6px;border:1px solid var(--border)">
                                    <div>
                                        <div style="font-size:12px;font-weight:600;color:var(--txt)">${escapeHTML(v.nombre)}</div>
                                        <div style="font-size:11px;color:var(--txt-muted)">
                                            ${escapeHTML(v.cargo_instancia)} · <span style="color:#60a5fa">${escapeHTML(v.consejo_nombre)}</span>
                                        </div>
                                    </div>
                                    <button onclick="removerVoceroInstancia(${inst.id}, ${v.vocero_id})" title="Desasignar" style="background:none;border:none;color:var(--red);cursor:pointer;padding:4px">
                                        <i data-lucide="trash-2" style="width:13px;height:13px"></i>
                                    </button>
                                </div>
                            `).join('')}
                        </div>
                    `}
                </div>
            </div>
        `).join('');
        lucide.createIcons();
    } catch (err) {
        container.innerHTML = `<div class="empty-state"><p style="color:var(--red)">Error al cargar instancias: ${escapeHTML(err.message)}</p></div>`;
    }
}

async function abrirModalAsignarInstancia(instanciaId, nombre) {
    document.getElementById('asig-instancia-id').value = instanciaId;
    document.getElementById('modal-asig-instancia-titulo').textContent = `Asignar Vocero Principal a: ${nombre}`;
    
    const select = document.getElementById('asig-instancia-vocero');
    select.innerHTML = '<option value="">Cargando voceros principales elegibles...</option>';
    openModal('modal-asignar-instancia');

    try {
        // Consultar candidatos con filtro estricto por comité homólogo de cada Consejo Comunal
        const voceros = await apiFetch(`/api/instancias/${instanciaId}/candidatos`);
        if (!voceros.length) {
            select.innerHTML = '<option value="">No hay voceros principales registrados en esta área</option>';
            return;
        }
        select.innerHTML = '<option value="">Seleccione vocero principal homólogo...</option>' +
            voceros.map(v => `<option value="${v.id}">${escapeHTML(v.nombre)} (C.I. ${escapeHTML(v.cedula || 'S/C')}) — CC ${escapeHTML(v.consejo_nombre)} [${escapeHTML(v.cargo)}]</option>`).join('');
    } catch (e) {
        select.innerHTML = '<option value="">Error cargando voceros elegibles</option>';
    }
}

async function guardarAsignacionInstancia(e) {
    e.preventDefault();
    const instId = document.getElementById('asig-instancia-id').value;
    const voceroId = document.getElementById('asig-instancia-vocero').value;
    const cargo = document.getElementById('asig-instancia-cargo').value.trim();

    if (!voceroId || !cargo) {
        toast('error', 'Por favor selecciona un vocero y especifica su cargo');
        return;
    }

    showLoading('Asignando vocero...');
    try {
        await apiFetch(`/api/instancias/${instId}/voceros`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                vocero_id: parseInt(voceroId),
                cargo_instancia: cargo,
                fecha_designacion: new Date().toISOString().slice(0, 10)
            })
        });
        toast('success', 'Vocero asignado exitosamente a la instancia');
        closeModal('modal-asignar-instancia');
        loadInstancias();
    } catch (err) {
        toast('error', err.message);
    } finally {
        hideLoading();
    }
}

async function removerVoceroInstancia(instanciaId, voceroId) {
    if (!confirm('¿Deseas retirar a este vocero de la instancia de gobierno?')) return;
    showLoading('Removiendo asignación...');
    try {
        await apiFetch(`/api/instancias/${instanciaId}/voceros/${voceroId}`, { method: 'DELETE' });
        toast('success', 'Vocero retirado de la instancia');
        loadInstancias();
    } catch (err) {
        toast('error', err.message);
    } finally {
        hideLoading();
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. COMISIONES DE GESTIÓN COMUNAL
// ─────────────────────────────────────────────────────────────────────────────

async function loadComisiones() {
    const container = document.getElementById('comisiones-list');
    if (!container) return;
    container.innerHTML = '<div class="empty-state"><div class="spinner"></div><p>Cargando comisiones de gestión...</p></div>';

    try {
        const comisiones = await apiFetch('/api/comisiones');
        if (!comisiones.length) {
            container.innerHTML = '<div class="empty-state"><p>No se encontraron comisiones registradas.</p></div>';
            return;
        }

        container.innerHTML = comisiones.map(c => `
            <div class="card" style="margin-bottom:14px">
                <div class="card-header" style="display:flex;justify-content:space-between;align-items:center">
                    <div>
                        <div class="card-title" style="font-size:15px;display:flex;align-items:center;gap:8px">
                            <i data-lucide="layers" style="color:#60a5fa;width:16px;height:16px"></i>
                            ${escapeHTML(c.nombre)}
                        </div>
                        <div style="font-size:12px;color:var(--txt-muted);margin-top:2px">
                            Área: ${escapeHTML(c.area_tematica || 'General')} · Responsable: <strong style="color:var(--txt)">${escapeHTML(c.responsable_nombre || 'Por designar')}</strong>
                        </div>
                    </div>
                    <button class="btn" onclick="abrirModalAsignarComision(${c.id}, '${escapeHTML(c.nombre)}')" style="font-size:11px;padding:5px 10px">
                        <i data-lucide="user-plus" style="width:13px;height:13px"></i>
                        <span>Asignar Miembro</span>
                    </button>
                </div>
                <div class="card-body" style="padding:14px">
                    <p style="font-size:12px;color:var(--txt-muted);margin-bottom:10px">
                        ${escapeHTML(c.descripcion || 'Sin descripción detallada')}
                    </p>
                    <div style="font-size:11px;font-weight:700;color:var(--txt-faint);text-transform:uppercase;margin-bottom:6px">
                        Voceros Adscritos (${c.miembros.length})
                    </div>
                    ${c.miembros.length === 0 ? `
                        <div style="font-size:12px;color:var(--txt-muted);padding:8px 0">No tiene voceros comisionados asignados aún.</div>
                    ` : `
                        <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(240px, 1fr));gap:8px">
                            ${c.miembros.map(m => `
                                <div style="display:flex;justify-content:space-between;align-items:center;padding:8px;background:var(--bg-card-2);border-radius:6px;border:1px solid var(--border)">
                                    <div>
                                        <div style="font-size:12px;font-weight:600;color:var(--txt)">${escapeHTML(m.nombre)}</div>
                                        <div style="font-size:11px;color:var(--txt-muted)">${escapeHTML(m.cargo_comision)} · ${escapeHTML(m.consejo_nombre)}</div>
                                    </div>
                                    <button onclick="removerVoceroComision(${c.id}, ${m.vocero_id})" style="background:none;border:none;color:var(--red);cursor:pointer">
                                        <i data-lucide="trash-2" style="width:13px;height:13px"></i>
                                    </button>
                                </div>
                            `).join('')}
                        </div>
                    `}
                </div>
            </div>
        `).join('');
        lucide.createIcons();
    } catch (err) {
        container.innerHTML = `<div class="empty-state"><p style="color:var(--red)">Error: ${escapeHTML(err.message)}</p></div>`;
    }
}

async function abrirModalAsignarComision(comisionId, nombre) {
    document.getElementById('asig-comision-id').value = comisionId;
    document.getElementById('modal-asig-comision-titulo').textContent = `Asignar Vocero Principal a: ${nombre}`;
    
    const select = document.getElementById('asig-comision-vocero');
    select.innerHTML = '<option value="">Cargando voceros de comités afines...</option>';
    openModal('modal-asignar-comision');

    try {
        // Consultar candidatos con filtro estricto por comité temático afín
        const voceros = await apiFetch(`/api/comisiones/${comisionId}/candidatos`);
        if (!voceros.length) {
            select.innerHTML = '<option value="">No hay voceros principales registrados en comités afines</option>';
            return;
        }
        select.innerHTML = '<option value="">Seleccione vocero principal afín...</option>' +
            voceros.map(v => `<option value="${v.id}">${escapeHTML(v.nombre)} (C.I. ${escapeHTML(v.cedula || 'S/C')}) — CC ${escapeHTML(v.consejo_nombre)} [${escapeHTML(v.cargo)}]</option>`).join('');
    } catch (e) {
        select.innerHTML = '<option value="">Error cargando voceros elegibles</option>';
    }
}

async function guardarAsignacionComision(e) {
    e.preventDefault();
    const comId = document.getElementById('asig-comision-id').value;
    const voceroId = document.getElementById('asig-comision-vocero').value;
    const cargo = document.getElementById('asig-comision-cargo').value.trim() || 'Miembro';

    if (!voceroId) {
        toast('error', 'Por favor selecciona un vocero');
        return;
    }

    showLoading('Asignando vocero a la comisión...');
    try {
        await apiFetch(`/api/comisiones/${comId}/voceros`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                vocero_id: parseInt(voceroId),
                cargo: cargo,
                fecha_inicio: new Date().toISOString().slice(0, 10)
            })
        });
        toast('success', 'Vocero asignado exitosamente a la comisión');
        closeModal('modal-asignar-comision');
        loadComisiones();
    } catch (err) {
        toast('error', err.message);
    } finally {
        hideLoading();
    }
}

async function removerVoceroComision(comisionId, voceroId) {
    if (!confirm('¿Deseas desincorporar al vocero de esta comisión de gestión?')) return;
    showLoading('Removiendo...');
    try {
        await apiFetch(`/api/comisiones/${comisionId}/voceros/${voceroId}`, { method: 'DELETE' });
        toast('success', 'Vocero desincorporado');
        loadComisiones();
    } catch (err) {
        toast('error', err.message);
    } finally {
        hideLoading();
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. CENSO COMUNAL
// ─────────────────────────────────────────────────────────────────────────────

let censoSubTabActivo = 'familias';

function switchCensoSubTab(tab) {
    censoSubTabActivo = tab;
    // Toggle button active states
    document.querySelectorAll('.censo-subtab-btn').forEach(b => b.classList.toggle('active', b.dataset.subtab === tab));
    // Toggle pane visibility with both class AND style.display to override any inline styles
    document.querySelectorAll('.censo-subtab-pane').forEach(p => {
        const isActive = p.id === `censo-subtab-${tab}`;
        p.classList.toggle('active', isActive);
        p.style.display = isActive ? 'block' : 'none';
    });

    if (tab === 'familias') loadCensoFamilias();
    if (tab === 'estadisticas') loadCensoEstadisticas();
    if (tab === 'electoral') loadCensoElectoral();
}

async function loadCenso() {
    // Cargar selector de consejos para filtros de censo
    try {
        const consejos = await apiFetch('/api/padron/consejos');
        const opts = '<option value="">Todos los Consejos Comunales</option>' +
            consejos.map(c => `<option value="${c.id}">${escapeHTML(c.nombre)}</option>`).join('');
        const f = document.getElementById('censo-filter-consejo');
        if (f) f.innerHTML = opts;
        const fc = document.getElementById('censo-modal-consejo');
        if (fc) fc.innerHTML = '<option value="">Seleccione Consejo Comunal...</option>' + consejos.map(c => `<option value="${c.id}">${escapeHTML(c.nombre)}</option>`).join('');
        const fe = document.getElementById('elector-modal-consejo');
        if (fe) fe.innerHTML = '<option value="">Seleccione Consejo Comunal...</option>' + consejos.map(c => `<option value="${c.id}">${escapeHTML(c.nombre)}</option>`).join('');
    } catch (e) {}

    switchCensoSubTab(censoSubTabActivo);
}

async function loadCensoFamilias() {
    const tbody = document.getElementById('censo-familias-tbody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="6"><div class="empty-state"><div class="spinner"></div><p>Cargando padrón censal...</p></div></td></tr>';

    const consejoId = document.getElementById('censo-filter-consejo')?.value || '';
    const busqueda = document.getElementById('censo-search')?.value.trim() || '';

    try {
        const params = new URLSearchParams();
        if (consejoId) params.set('consejo_id', consejoId);
        if (busqueda) params.set('busqueda', busqueda);

        const data = await apiFetch(`/api/censo/familias?${params}`);
        document.getElementById('censo-familias-count').textContent = `${data.total} familia${data.total !== 1 ? 's' : ''}`;

        if (!data.familias || !data.familias.length) {
            tbody.innerHTML = '<tr><td colspan="6"><div class="empty-state"><p>No se encontraron familias registradas con estos filtros.</p></div></td></tr>';
            return;
        }

        tbody.innerHTML = data.familias.map(f => `
            <tr>
                <td><strong style="color:#60a5fa;font-family:var(--font-mono)">${escapeHTML(f.familia_codigo || '—')}</strong></td>
                <td>
                    <div style="font-weight:600;color:var(--txt)">${escapeHTML(f.jefe_familia)}</div>
                    <div style="font-size:11px;color:var(--txt-muted)">C.I. ${escapeHTML(f.cedula_jefe || '—')}</div>
                </td>
                <td style="font-size:12px;color:var(--txt-muted)">${escapeHTML(f.consejo_nombre || '—')}</td>
                <td style="font-size:12px">${escapeHTML(f.direccion || '—')}</td>
                <td style="text-align:center"><span class="badge" style="background:rgba(37,99,235,0.15);color:#60a5fa">${f.total_integrantes} hab.</span></td>
                <td>
                    <button class="btn" onclick="verDetalleFamilia(${f.id})" style="font-size:11px;padding:3px 8px">
                        Ver Ficha
                    </button>
                </td>
            </tr>
        `).join('');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><p style="color:var(--red)">Error: ${escapeHTML(err.message)}</p></div></td></tr>`;
    }
}

async function verDetalleFamilia(censoId) {
    showLoading('Cargando expediente familiar...');
    try {
        const fam = await apiFetch(`/api/censo/familias/${censoId}`);
        const modal = document.getElementById('modal-detalle-familia');
        document.getElementById('fam-det-codigo').textContent = fam.familia_codigo || 'Expediente';
        document.getElementById('fam-det-jefe').textContent = fam.jefe_familia;
        document.getElementById('fam-det-cedula').textContent = fam.cedula_jefe || '—';
        document.getElementById('fam-det-consejo').textContent = fam.consejo_nombre || '—';
        document.getElementById('fam-det-direccion').textContent = fam.direccion || '—';
        document.getElementById('fam-det-telefono').textContent = fam.telefono || '—';

        // Miembros
        const miembrosContainer = document.getElementById('fam-det-miembros');
        if (fam.miembros && fam.miembros.length) {
            miembrosContainer.innerHTML = fam.miembros.map((m, i) => `
                <tr style="font-size:12px">
                    <td>${i + 1}</td>
                    <td><strong>${escapeHTML(m.nombre_completo)}</strong></td>
                    <td>${escapeHTML(m.cedula || '—')}</td>
                    <td>${escapeHTML(m.parentesco || '—')}</td>
                    <td>${escapeHTML(m.sexo || '—')}</td>
                    <td>${escapeHTML(m.ocupacion || '—')}</td>
                    <td>
                        ${m.tipo_discapacidad ? `<span class="badge" style="background:rgba(239,68,68,0.15);color:#ef4444">${escapeHTML(m.tipo_discapacidad)}</span>` : '<span style="color:var(--txt-faint)">Ninguna</span>'}
                    </td>
                </tr>
            `).join('');
        } else {
            miembrosContainer.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--txt-muted);padding:10px">Sin miembros registrados</td></tr>';
        }

        // Vivienda y servicios
        const vivContainer = document.getElementById('fam-det-vivienda');
        if (fam.vivienda) {
            const v = fam.vivienda;
            vivContainer.innerHTML = `
                <div style="font-size:12px;display:grid;grid-template-columns:1fr 1fr;gap:8px">
                    <div><strong>Tipo:</strong> ${escapeHTML(v.tipo_vivienda || '—')}</div>
                    <div><strong>Tenencia:</strong> ${escapeHTML(v.tenencia || '—')}</div>
                    <div><strong>Paredes:</strong> ${escapeHTML(v.material_paredes || '—')}</div>
                    <div><strong>Techo:</strong> ${escapeHTML(v.material_techo || '—')}</div>
                    <div><strong>Piso:</strong> ${escapeHTML(v.material_piso || '—')}</div>
                    <div><strong>Habitaciones:</strong> ${v.num_habitaciones}</div>
                    <div><strong>Estado:</strong> <span class="badge">${escapeHTML(v.estado_general || 'Regular')}</span></div>
                </div>
                ${v.servicios && v.servicios.length ? `
                    <div style="margin-top:12px">
                        <strong style="font-size:11px;color:var(--txt-faint);text-transform:uppercase">Servicios Domiciliarios:</strong>
                        <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px">
                            ${v.servicios.map(s => `
                                <span class="badge" style="background:${s.tiene ? 'rgba(34,197,94,0.12);color:#22c55e' : 'rgba(239,68,68,0.12);color:#ef4444'}">
                                    ${escapeHTML(s.servicio)}: ${s.tiene ? escapeHTML(s.frecuencia || 'Sí') : 'No'}
                                </span>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            `;
        } else {
            vivContainer.innerHTML = '<p style="font-size:12px;color:var(--txt-muted)">Datos de vivienda no registrados.</p>';
        }

        openModal('modal-detalle-familia');
        lucide.createIcons();
    } catch (err) {
        toast('error', err.message);
    } finally {
        hideLoading();
    }
}

async function loadCensoEstadisticas() {
    const container = document.getElementById('censo-stats-container');
    if (!container) return;
    container.innerHTML = '<div class="empty-state"><div class="spinner"></div><p>Calculando estadísticas censales...</p></div>';

    try {
        const stats = await apiFetch('/api/censo/estadisticas');
        container.innerHTML = `
            <div class="kpi-row" style="margin-bottom:20px">
                <div class="kpi-card blue">
                    <div class="kpi-icon"><i data-lucide="home"></i></div>
                    <div class="kpi-value">${stats.total_familias}</div>
                    <div class="kpi-label">Familias Registradas</div>
                </div>
                <div class="kpi-card green">
                    <div class="kpi-icon"><i data-lucide="users"></i></div>
                    <div class="kpi-value">${stats.total_habitantes}</div>
                    <div class="kpi-label">Habitantes Totales</div>
                </div>
                <div class="kpi-card purple">
                    <div class="kpi-icon"><i data-lucide="user-check"></i></div>
                    <div class="kpi-value">${stats.por_sexo['F'] || 0} / ${stats.por_sexo['M'] || 0}</div>
                    <div class="kpi-label">Mujeres / Hombres</div>
                </div>
                <div class="kpi-card gold">
                    <div class="kpi-icon"><i data-lucide="heart"></i></div>
                    <div class="kpi-value">${stats.total_discapacitados}</div>
                    <div class="kpi-label">Pers. con Discapacidad</div>
                </div>
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
                <div class="card">
                    <div class="card-header"><div class="card-title"><i data-lucide="map-pin"></i> Habitantes por Consejo Comunal</div></div>
                    <div class="card-body" style="padding:14px">
                        <table class="table" style="font-size:12px">
                            <thead><tr><th>Consejo Comunal</th><th style="text-align:right">Familias</th><th style="text-align:right">Habitantes</th></tr></thead>
                            <tbody>
                                ${stats.por_consejo.map(c => `
                                    <tr>
                                        <td><strong>${escapeHTML(c.nombre)}</strong></td>
                                        <td style="text-align:right">${c.familias}</td>
                                        <td style="text-align:right"><span class="badge" style="background:var(--accent-glow);color:#60a5fa">${c.habitantes}</span></td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header"><div class="card-title"><i data-lucide="activity"></i> Atención a la Discapacidad</div></div>
                    <div class="card-body" style="padding:14px">
                        ${stats.discapacidades_tipo.length === 0 ? '<p style="font-size:12px;color:var(--txt-muted)">Sin discapacidades registradas en el censo.</p>' : `
                            <table class="table" style="font-size:12px">
                                <thead><tr><th>Tipo de Discapacidad</th><th style="text-align:right">Casos</th></tr></thead>
                                <tbody>
                                    ${stats.discapacidades_tipo.map(d => `
                                        <tr>
                                            <td>${escapeHTML(d.tipo)}</td>
                                            <td style="text-align:right"><strong style="color:var(--red)">${d.cantidad}</strong></td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        `}
                    </div>
                </div>
            </div>
        `;
        lucide.createIcons();
    } catch (err) {
        container.innerHTML = `<div class="empty-state"><p style="color:var(--red)">Error: ${escapeHTML(err.message)}</p></div>`;
    }
}

async function loadCensoElectoral() {
    const tbody = document.getElementById('censo-electoral-tbody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="5"><div class="empty-state"><div class="spinner"></div><p>Cargando padrón electoral...</p></div></td></tr>';

    try {
        const data = await apiFetch('/api/censo/electoral');
        document.getElementById('censo-electoral-count').textContent = `${data.total} elector${data.total !== 1 ? 'es' : ''}`;

        if (!data.electores || !data.electores.length) {
            tbody.innerHTML = '<tr><td colspan="5"><div class="empty-state"><p>No hay electores registrados aún en el padrón electoral comunal.</p></div></td></tr>';
            return;
        }

        tbody.innerHTML = data.electores.map((e, idx) => `
            <tr>
                <td>${idx + 1}</td>
                <td><strong>${escapeHTML(e.nombre)}</strong></td>
                <td>${escapeHTML(e.cedula)}</td>
                <td style="font-size:12px;color:var(--txt-muted)">${escapeHTML(e.consejo_nombre || '—')}</td>
                <td><span class="badge" style="background:rgba(34,197,94,0.12);color:#22c55e">Habilitado</span></td>
            </tr>
        `).join('');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state"><p style="color:var(--red)">Error: ${escapeHTML(err.message)}</p></div></td></tr>`;
    }
}

async function guardarNuevaFamilia(e) {
    e.preventDefault();
    const consejoId = document.getElementById('censo-modal-consejo').value;
    const jefe = document.getElementById('fam-input-jefe').value.trim();
    const cedula = document.getElementById('fam-input-cedula').value.trim();
    const direccion = document.getElementById('fam-input-direccion').value.trim();
    const telefono = document.getElementById('fam-input-telefono').value.trim();

    if (!consejoId || !jefe) {
        toast('error', 'Seleccione el consejo comunal e indique el nombre del jefe de familia');
        return;
    }

    showLoading('Registrando familia en el censo...');
    try {
        await apiFetch('/api/censo/familias', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                consejo_id: parseInt(consejoId),
                jefe_familia: jefe,
                cedula_jefe: cedula,
                direccion: direccion,
                telefono: telefono,
                miembros: [
                    {
                        nombre_completo: jefe,
                        cedula: cedula,
                        parentesco: 'Jefe de Familia',
                        sexo: 'M'
                    }
                ],
                vivienda: {
                    tipo_vivienda: 'Casa',
                    tenencia: 'Propia',
                    estado_general: 'Bueno'
                },
                servicios: [
                    { servicio: 'Agua potable', tiene: 1, frecuencia: 'Intermitente' },
                    { servicio: 'Electricidad', tiene: 1, frecuencia: 'Continuo' },
                    { servicio: 'Gas comunal', tiene: 1, frecuencia: 'Mensual' }
                ]
            })
        });
        toast('success', 'Familia registrada en el censo comunal');
        closeModal('modal-nueva-familia');
        document.getElementById('form-nueva-familia').reset();
        loadCensoFamilias();
    } catch (err) {
        toast('error', err.message);
    } finally {
        hideLoading();
    }
}

async function guardarNuevoElector(e) {
    e.preventDefault();
    const consejoId = document.getElementById('elector-modal-consejo').value;
    const nombre = document.getElementById('elector-input-nombre').value.trim();
    const cedula = document.getElementById('elector-input-cedula').value.trim();

    if (!consejoId || !nombre || !cedula) {
        toast('error', 'Complete los datos obligatorios del elector');
        return;
    }

    showLoading('Registrando elector comunal...');
    try {
        await apiFetch('/api/censo/electoral', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                consejo_id: parseInt(consejoId),
                nombre: nombre,
                cedula: cedula,
                habilitado: 1
            })
        });
        toast('success', 'Elector registrado en el censo electoral');
        closeModal('modal-nuevo-elector');
        document.getElementById('form-nuevo-elector').reset();
        loadCensoElectoral();
    } catch (err) {
        toast('error', err.message);
    } finally {
        hideLoading();
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. RENDICIÓN DE CUENTAS (Art. 52 LOC)
// ─────────────────────────────────────────────────────────────────────────────

async function loadRendiciones() {
    const list = document.getElementById('rendiciones-list');
    if (!list) return;
    list.innerHTML = '<div class="empty-state"><div class="spinner"></div><p>Cargando rendiciones de cuentas...</p></div>';

    // Cargar selector de instancias en el modal de nueva rendición
    try {
        const instancias = await apiFetch('/api/instancias');
        const opts = '<option value="">Seleccionar Instancia Responsable...</option>' +
            instancias.map(i => `<option value="${i.id}">${escapeHTML(i.nombre)}</option>`).join('');
        const sel = document.getElementById('rend-modal-instancia');
        if (sel) sel.innerHTML = opts;
    } catch (e) {}

    try {
        // Cargar resumen financiero
        const res = await apiFetch('/api/rendiciones/resumen');
        document.getElementById('kpi-rend-total').textContent = res.total_rendiciones || 0;
        document.getElementById('kpi-rend-asignado').textContent = (res.total_asignado || 0).toLocaleString('es-VE', { style: 'currency', currency: 'VES' });
        document.getElementById('kpi-rend-ejecutado').textContent = (res.total_ejecutado || 0).toLocaleString('es-VE', { style: 'currency', currency: 'VES' });
        document.getElementById('kpi-rend-aprobadas').textContent = `${res.total_aprobadas || 0} / ${res.total_rendiciones || 0}`;

        // Cargar listado
        const rendiciones = await apiFetch('/api/rendiciones');
        if (!rendiciones.length) {
            list.innerHTML = '<div class="empty-state"><p>No hay rendiciones de cuentas asentadas para el período actual.</p></div>';
            return;
        }

        list.innerHTML = rendiciones.map(r => {
            const estadoBadge = r.aprobada === 1 
                ? '<span class="badge" style="background:rgba(34,197,94,0.15);color:#22c55e">Aprobada por Parlamento</span>'
                : r.aprobada === 2
                ? '<span class="badge" style="background:rgba(239,68,68,0.15);color:#ef4444">Observada / Rechazada</span>'
                : '<span class="badge" style="background:rgba(251,191,36,0.15);color:#fbbf24">En Revisión / Pendiente</span>';

            return `
                <div class="card" style="margin-bottom:12px;padding:16px">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start">
                        <div>
                            <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
                                <span class="badge" style="background:var(--accent-glow);color:#60a5fa">${escapeHTML(r.periodo)}</span>
                                <span style="font-size:12px;color:var(--txt-muted)">${escapeHTML(r.tipo)} · Fecha: ${escapeHTML(r.fecha_rendicion)}</span>
                                ${estadoBadge}
                            </div>
                            <h4 style="font-size:14px;font-weight:700;color:var(--txt)">
                                ${escapeHTML(r.instancia_nombre || r.comision_nombre || 'Instancia Comunal')}
                            </h4>
                        </div>
                        <div style="text-align:right">
                            <div style="font-size:11px;color:var(--txt-muted)">Ejecutado / Asignado</div>
                            <div style="font-size:14px;font-weight:700;color:var(--green)">
                                ${r.presupuesto_ejecutado.toLocaleString('es-VE')} <span style="font-size:11px;color:var(--txt-faint)">/ ${r.presupuesto_asignado.toLocaleString('es-VE')} Bs.</span>
                            </div>
                        </div>
                    </div>
                    <div style="font-size:13px;color:var(--txt);margin-top:10px;line-height:1.5">
                        ${escapeHTML(r.descripcion_logros)}
                    </div>
                    ${r.observaciones ? `
                        <div style="margin-top:8px;padding:8px 12px;background:rgba(255,255,255,0.02);border-left:2px solid var(--accent);font-size:12px;color:var(--txt-muted)">
                            <strong>Observaciones de Contraloría:</strong> ${escapeHTML(r.observaciones)}
                        </div>
                    ` : ''}
                    <div style="display:flex;gap:8px;margin-top:12px;justify-content:flex-end">
                        <button class="btn" onclick="aprobarRendicion(${r.id}, 1)" style="font-size:11px;padding:4px 8px;color:#22c55e">
                            <i data-lucide="check" style="width:12px;height:12px"></i> Aprobar
                        </button>
                        <button class="btn" onclick="aprobarRendicion(${r.id}, 2)" style="font-size:11px;padding:4px 8px;color:#ef4444">
                            <i data-lucide="x" style="width:12px;height:12px"></i> Rechazar
                        </button>
                    </div>
                </div>
            `;
        }).join('');
        lucide.createIcons();
    } catch (err) {
        list.innerHTML = `<div class="empty-state"><p style="color:var(--red)">Error: ${escapeHTML(err.message)}</p></div>`;
    }
}

async function guardarNuevaRendicion(e) {
    e.preventDefault();
    const periodo = document.getElementById('rend-input-periodo').value.trim();
    const instanciaId = document.getElementById('rend-modal-instancia').value;
    const asignado = parseFloat(document.getElementById('rend-input-asignado').value) || 0;
    const ejecutado = parseFloat(document.getElementById('rend-input-ejecutado').value) || 0;
    const logros = document.getElementById('rend-input-logros').value.trim();

    if (!periodo || !logros) {
        toast('error', 'Indique el período y la memoria de logros');
        return;
    }

    showLoading('Guardando rendición de cuentas...');
    try {
        await apiFetch('/api/rendiciones', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                periodo: periodo,
                instancia_id: instanciaId ? parseInt(instanciaId) : null,
                tipo: 'Ordinaria',
                fecha_rendicion: new Date().toISOString().slice(0, 10),
                presupuesto_asignado: asignado,
                presupuesto_ejecutado: ejecutado,
                descripcion_logros: logros,
                aprobada: 0
            })
        });
        toast('success', 'Rendición de cuentas asentada');
        closeModal('modal-nueva-rendicion');
        document.getElementById('form-nueva-rendicion').reset();
        loadRendiciones();
    } catch (err) {
        toast('error', err.message);
    } finally {
        hideLoading();
    }
}

async function aprobarRendicion(id, nuevoEstado) {
    const motivo = prompt('Comentario u observaciones del dictamen:');
    if (motivo === null) return;
    showLoading('Actualizando estado de la rendición...');
    try {
        await apiFetch(`/api/rendiciones/${id}/aprobar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ aprobada: nuevoEstado, observaciones: motivo })
        });
        toast('success', 'Estado de rendición actualizado');
        loadRendiciones();
    } catch (err) {
        toast('error', err.message);
    } finally {
        hideLoading();
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. GACETA COMUNAL (Art. 41 LOC)
// ─────────────────────────────────────────────────────────────────────────────

async function loadGaceta() {
    const list = document.getElementById('gaceta-list');
    if (!list) return;
    list.innerHTML = '<div class="empty-state"><div class="spinner"></div><p>Cargando Gaceta Comunal...</p></div>';

    // Obtener siguiente correlativo sugerido
    try {
        const corr = await apiFetch('/api/gaceta/siguiente-numero');
        const numInput = document.getElementById('gaceta-input-numero');
        if (numInput) numInput.placeholder = corr.numero;
    } catch (e) {}

    try {
        const decisiones = await apiFetch('/api/gaceta');
        document.getElementById('gaceta-count').textContent = `${decisiones.length} publicación${decisiones.length !== 1 ? 'es' : ''}`;

        if (!decisiones.length) {
            list.innerHTML = '<div class="empty-state"><p>No se registran publicaciones ni leyes promulgadas en la Gaceta Comunal aún.</p></div>';
            return;
        }

        list.innerHTML = decisiones.map(d => `
            <div class="card" style="margin-bottom:12px;padding:16px">
                <div style="display:flex;justify-content:space-between;align-items:flex-start">
                    <div>
                        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
                            <span class="badge" style="background:rgba(239,68,68,0.15);color:#ef4444;font-family:var(--font-mono);font-weight:700">
                                ${escapeHTML(d.numero)}
                            </span>
                            <span class="badge" style="background:var(--accent-glow);color:#60a5fa">${escapeHTML(d.tipo_decision)}</span>
                            <span style="font-size:12px;color:var(--txt-muted)">Promulgada: ${escapeHTML(d.fecha)}</span>
                        </div>
                        <h4 style="font-size:15px;font-weight:700;color:var(--txt)">
                            ${escapeHTML(d.titulo)}
                        </h4>
                        <div style="font-size:11px;color:var(--txt-muted);margin-top:2px">
                            Aprobado por: ${escapeHTML(d.aprobado_por || 'Parlamento Comunal')} · Sesión: ${escapeHTML(d.parlamento_sesion || 'Ordinaria')}
                        </div>
                    </div>
                    <button class="btn btn-primary" onclick="descargarPdfGaceta(${d.id})" style="font-size:11px;padding:6px 12px">
                        <i data-lucide="file-text" style="width:13px;height:13px"></i>
                        <span>Generar PDF</span>
                    </button>
                </div>
                <div style="font-size:13px;color:var(--txt);margin-top:12px;background:var(--bg-card-2);padding:12px;border-radius:6px;border:1px solid var(--border);max-height:160px;overflow-y:auto;white-space:pre-wrap;font-family:inherit">
                    ${escapeHTML(d.contenido)}
                </div>
            </div>
        `).join('');
        lucide.createIcons();
    } catch (err) {
        list.innerHTML = `<div class="empty-state"><p style="color:var(--red)">Error: ${escapeHTML(err.message)}</p></div>`;
    }
}

async function guardarNuevaGaceta(e) {
    e.preventDefault();
    const titulo = document.getElementById('gaceta-input-titulo').value.trim();
    const tipo = document.getElementById('gaceta-input-tipo').value;
    const sesion = document.getElementById('gaceta-input-sesion').value.trim();
    const contenido = document.getElementById('gaceta-input-contenido').value.trim();

    if (!titulo || !contenido) {
        toast('error', 'El título y el texto del acuerdo son requeridos');
        return;
    }

    showLoading('Promulgando en Gaceta Comunal...');
    try {
        await apiFetch('/api/gaceta', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                titulo: titulo,
                tipo_decision: tipo,
                parlamento_sesion: sesion,
                contenido: contenido,
                fecha: new Date().toISOString().slice(0, 10),
                aprobado_por: 'Parlamento Comunal CPPO'
            })
        });
        toast('success', 'Publicación promulgada en Gaceta Oficial Comunal');
        closeModal('modal-nueva-gaceta');
        document.getElementById('form-nueva-gaceta').reset();
        loadGaceta();
    } catch (err) {
        toast('error', err.message);
    } finally {
        hideLoading();
    }
}

async function descargarPdfGaceta(gacetaId) {
    showLoading('Generando documento oficial en PDF...');
    try {
        const res = await apiFetch(`/api/gaceta/${gacetaId}/pdf`);
        toast('success', 'PDF oficial generado exitosamente');
        window.open(res.pdf_url, '_blank');
    } catch (err) {
        toast('error', err.message);
    } finally {
        hideLoading();
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// 6. PROYECTOS ACA (Agenda Concreta de Acción - Matriz 7T)
// ─────────────────────────────────────────────────────────────────────────────

async function loadProyectos() {
    const list = document.getElementById('proyectos-grid');
    if (!list) return;
    list.innerHTML = '<div class="empty-state"><div class="spinner"></div><p>Cargando Agenda Concreta de Acción (7T)...</p></div>';

    // Cargar comisiones en selectores
    try {
        const comisiones = await apiFetch('/api/comisiones');
        const sel = document.getElementById('proy-modal-comision');
        if (sel) sel.innerHTML = '<option value="">Seleccione Comisión Rectora...</option>' + comisiones.map(c => `<option value="${c.id}">${escapeHTML(c.nombre)}</option>`).join('');
    } catch (e) {}

    try {
        const dash = await apiFetch('/api/proyectos/dashboard');
        document.getElementById('kpi-proy-total').textContent = dash.total_proyectos || 0;
        document.getElementById('kpi-proy-inversion').textContent = (dash.inversion_total_estimada || 0).toLocaleString('es-VE', { style: 'currency', currency: 'VES' });
        document.getElementById('kpi-proy-avance').textContent = `${Math.round(dash.avance_promedio || 0)}%`;
        document.getElementById('kpi-proy-beneficiarios').textContent = (dash.total_beneficiarios || 0).toLocaleString();

        const proyectos = await apiFetch('/api/proyectos');
        if (!proyectos.length) {
            list.innerHTML = `
                <div class="empty-state" style="grid-column:1/-1;text-align:center;padding:40px 20px">
                    <i data-lucide="file-spreadsheet" style="width:48px;height:48px;color:var(--txt-muted);margin-bottom:12px"></i>
                    <h4 style="font-size:16px;color:var(--txt);margin-bottom:6px">No hay proyectos asentados en la Agenda Concreta de Acción</h4>
                    <p style="font-size:13px;color:var(--txt-muted);max-width:500px;margin:0 auto 16px">
                        Puedes registrar nudos críticos y acciones manualmente, o importar directamente el archivo del Plan de la Patria Comunal (.docx).
                    </p>
                    <div style="display:flex;gap:10px;justify-content:center">
                        <button class="btn btn-primary" onclick="openModal('modal-nuevo-proyecto')">
                            <i data-lucide="plus"></i> Registrar Acción ACA
                        </button>
                        <button class="btn" onclick="document.getElementById('input-importar-docx').click()">
                            <i data-lucide="upload"></i> Importar Matriz .DOCX
                        </button>
                    </div>
                </div>
            `;
            lucide.createIcons();
            return;
        }

        list.innerHTML = proyectos.map(p => {
            const estadoColor = p.estado === 'completado' ? '#22c55e' : p.estado === 'en_ejecucion' ? '#60a5fa' : '#fbbf24';
            const t7t = p.transformacion_7t || 'General';
            return `
                <div class="card" style="display:flex;flex-direction:column;justify-content:space-between;padding:16px;position:relative">
                    <div style="border-bottom:1px solid var(--border);padding-bottom:12px">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start">
                            <div>
                                <span class="badge" style="background:var(--accent-glow);color:#60a5fa;font-family:var(--font-mono);font-size:10px">
                                    ${escapeHTML(p.codigo_proyecto || 'ACA')}
                                </span>
                                <span class="badge" style="background:rgba(255,255,255,0.05);color:${estadoColor};font-size:10px">
                                    ${escapeHTML(p.estado.toUpperCase().replace('_', ' '))}
                                </span>
                            </div>
                            <div style="display:flex;gap:4px">
                                <button class="btn" onclick="editarProyectoPrompt(${p.id})" title="Editar" style="padding:3px 6px;font-size:11px">
                                    <i data-lucide="edit-2" style="width:12px;height:12px"></i>
                                </button>
                                <button class="btn" onclick="eliminarProyectoAca(${p.id})" title="Eliminar" style="padding:3px 6px;font-size:11px;color:var(--red)">
                                    <i data-lucide="trash-2" style="width:12px;height:12px"></i>
                                </button>
                            </div>
                        </div>
                        <div style="font-size:11px;font-weight:700;color:var(--accent);margin-top:6px;text-transform:uppercase">
                            ${escapeHTML(t7t)}
                        </div>
                        <h4 style="font-size:14px;font-weight:700;color:var(--txt);margin-top:4px">
                            ${escapeHTML(p.accion_ejecutar || p.nombre)}
                        </h4>
                    </div>

                    <div style="padding:12px 0;flex:1;font-size:12px">
                        ${p.nudo_critico ? `
                            <div style="margin-bottom:8px">
                                <strong style="color:var(--txt-muted);font-size:11px">Nudo Crítico / Problema:</strong>
                                <div style="color:var(--txt);margin-top:2px">${escapeHTML(p.nudo_critico)}</div>
                            </div>
                        ` : ''}
                        ${p.potencialidades ? `
                            <div style="margin-bottom:8px">
                                <strong style="color:var(--txt-muted);font-size:11px">Potencialidad Local:</strong>
                                <div style="color:var(--txt);margin-top:2px">${escapeHTML(p.potencialidades)}</div>
                            </div>
                        ` : ''}
                        ${p.requerimiento ? `
                            <div style="margin-bottom:8px">
                                <strong style="color:var(--txt-muted);font-size:11px">Requerimientos / Materiales:</strong>
                                <div style="color:var(--txt);margin-top:2px">${escapeHTML(p.requerimiento)}</div>
                            </div>
                        ` : ''}
                        
                        <div style="display:flex;gap:12px;font-size:11px;color:var(--txt-muted);margin-top:8px">
                            <span>⏱️ ${escapeHTML(p.tiempo_ejecucion || 'Corto Plazo')}</span>
                            ${p.voceria_vinculada ? `<span>👥 ${escapeHTML(p.voceria_vinculada)}</span>` : ''}
                        </div>

                        <!-- Barra de progreso -->
                        <div style="margin-top:12px">
                            <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:4px">
                                <span style="color:var(--txt-muted)">Avance físico</span>
                                <strong style="color:${estadoColor}">${p.porcentaje_avance}%</strong>
                            </div>
                            <div style="width:100%;height:6px;background:var(--border);border-radius:3px;overflow:hidden">
                                <div style="width:${p.porcentaje_avance}%;height:100%;background:${estadoColor};transition:width 0.3s"></div>
                            </div>
                        </div>
                    </div>

                    <div style="padding-top:10px;border-top:1px solid var(--border);display:flex;justify-content:space-between;align-items:center">
                        <span style="font-size:11px;color:var(--txt-muted)">
                            ${p.monto_estimado ? `${p.monto_estimado.toLocaleString('es-VE')} Bs.` : ''}
                        </span>
                        <button class="btn" onclick="actualizarAvanceProyecto(${p.id}, ${p.porcentaje_avance})" style="font-size:11px;padding:4px 8px">
                            <i data-lucide="percent" style="width:11px;height:11px"></i> Avance
                        </button>
                    </div>
                </div>
            `;
        }).join('');
        lucide.createIcons();
    } catch (err) {
        list.innerHTML = `<div class="empty-state"><p style="color:var(--red)">Error: ${escapeHTML(err.message)}</p></div>`;
    }
}

async function guardarNuevoProyecto(e) {
    e.preventDefault();
    const nombre = document.getElementById('proy-input-nombre').value.trim();
    const t7t = document.getElementById('proy-input-7t') ? document.getElementById('proy-input-7t').value : '';
    const nudo = document.getElementById('proy-input-nudo') ? document.getElementById('proy-input-nudo').value.trim() : '';
    const potencial = document.getElementById('proy-input-potencial') ? document.getElementById('proy-input-potencial').value.trim() : '';
    const reqMat = document.getElementById('proy-input-requerimiento') ? document.getElementById('proy-input-requerimiento').value.trim() : '';
    const plazo = document.getElementById('proy-input-plazo') ? document.getElementById('proy-input-plazo').value : 'Corto Plazo';
    const comisionId = document.getElementById('proy-modal-comision').value;
    const monto = parseFloat(document.getElementById('proy-input-monto').value) || 0;
    const beneficiarios = parseInt(document.getElementById('proy-input-beneficiarios').value) || 0;
    const descripcion = document.getElementById('proy-input-desc').value.trim();

    if (!nombre) {
        toast('error', 'Indique la acción u obra a ejecutar');
        return;
    }

    showLoading('Guardando acción en la Agenda Concreta de Acción...');
    try {
        await apiFetch('/api/proyectos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                nombre: nombre,
                transformacion_7t: t7t,
                accion_ejecutar: nombre,
                nudo_critico: nudo,
                potencialidades: potencial,
                requerimiento: reqMat,
                tiempo_ejecucion: plazo,
                comision_id: comisionId ? parseInt(comisionId) : null,
                monto_estimado: monto,
                beneficiarios: beneficiarios,
                descripcion: descripcion || nudo,
                estado: 'planificado',
                porcentaje_avance: 0
            })
        });
        toast('success', 'Proyecto/Acción guardada en el Plan ACA');
        closeModal('modal-nuevo-proyecto');
        document.getElementById('form-nuevo-proyecto').reset();
        loadProyectos();
    } catch (err) {
        toast('error', err.message);
    } finally {
        hideLoading();
    }
}

async function eliminarProyectoAca(id) {
    if (!confirm('¿Deseas eliminar esta acción o nudo crítico de la Agenda Concreta de Acción?')) return;
    showLoading('Eliminando...');
    try {
        await apiFetch(`/api/proyectos/${id}`, { method: 'DELETE' });
        toast('success', 'Acción eliminada exitosamente');
        loadProyectos();
    } catch (err) {
        toast('error', err.message);
    } finally {
        hideLoading();
    }
}

async function editarProyectoPrompt(id) {
    showLoading('Cargando datos...');
    try {
        const p = await apiFetch(`/api/proyectos/${id}`);
        hideLoading();
        const nuevoNombre = prompt('Editar Acción / Obra a Ejecutar:', p.accion_ejecutar || p.nombre);
        if (nuevoNombre === null) return;
        const nuevoNudo = prompt('Editar Nudo Crítico / Problema:', p.nudo_critico || '');
        if (nuevoNudo === null) return;
        const nuevosReq = prompt('Editar Requerimientos / Materiales:', p.requerimiento || '');
        if (nuevosReq === null) return;

        showLoading('Actualizando acción...');
        await apiFetch(`/api/proyectos/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                nombre: nuevoNombre,
                accion_ejecutar: nuevoNombre,
                nudo_critico: nuevoNudo,
                requerimiento: nuevosReq
            })
        });
        toast('success', 'Acción actualizada exitosamente');
        loadProyectos();
    } catch (err) {
        toast('error', err.message);
    } finally {
        hideLoading();
    }
}

async function importarArchivoDocx(input) {
    if (!input.files || !input.files[0]) return;
    const file = input.files[0];
    const formData = new FormData();
    formData.append('file', file);

    showLoading('Extrayendo tabla del Plan de la Patria Comunal (.docx)...');
    try {
        const res = await apiFetch('/api/proyectos/importar-docx', {
            method: 'POST',
            body: formData
        });

        if (!res.proyectos || !res.proyectos.length) {
            toast('error', 'No se encontraron filas con datos en las tablas del archivo');
            return;
        }

        const confirmMsg = `Se detectaron ${res.proyectos.length} acciones / proyectos en el archivo Word.\n¿Deseas importarlos a la Agenda Concreta de Acción?`;
        if (!confirm(confirmMsg)) return;

        // Guardar cada proyecto en base de datos
        let guardados = 0;
        for (const pr of res.proyectos) {
            try {
                await apiFetch('/api/proyectos', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(pr)
                });
                guardados++;
            } catch (e) {}
        }

        toast('success', `¡Éxito! Se importaron ${guardados} proyectos del Plan de la Patria Comunal.`);
        loadProyectos();
    } catch (err) {
        toast('error', `Error al importar: ${err.message}`);
    } finally {
        hideLoading();
        input.value = '';
    }
}

async function actualizarAvanceProyecto(id, actual) {
    const nuevo = prompt('Nuevo porcentaje de avance (0 a 100):', actual);
    if (nuevo === null) return;
    const p = parseInt(nuevo);
    if (isNaN(p) || p < 0 || p > 100) {
        toast('error', 'Por favor ingrese un número válido entre 0 y 100');
        return;
    }

    showLoading('Actualizando progreso...');
    try {
        await apiFetch(`/api/proyectos/${id}/avance`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ porcentaje_avance: p })
        });
        toast('success', 'Avance del proyecto actualizado');
        loadProyectos();
    } catch (err) {
        toast('error', err.message);
    } finally {
        hideLoading();
    }
}
