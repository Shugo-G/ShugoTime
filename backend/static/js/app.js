/* ShugoClock — Frontend SPA */

const API = '/api';

// ─── Estado global ───────────────────────────────────────────────────────────
let currentUser = null; // null = invitado, {username} = admin

let estado = {
  en_progreso: false,
  ciclo_activo: null,
  ultimo_ciclo: null,
};
let logPollingTimer = null;
let estadoPollingTimer = null;
let lastLogId = 0;
let logCicloId = null;
let logRelojFiltro = '';
let autoScroll = true;

// ─── Utilidades ──────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  const data = res.ok ? await res.json().catch(() => null) : null;
  if (!res.ok) throw { status: res.status, data };
  return data;
}

function getCookie(name) {
  const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return v ? v.pop() : '';
}

function toast(msg, type = 'ok') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 3500);
}

function badgeEstado(estado, activo) {
  if (!activo) return '<span class="badge badge-inactivo">Inactivo</span>';
  if (estado === 'ok')        return '<span class="badge badge-ok">OK</span>';
  if (estado === 'error')     return '<span class="badge badge-error">Error</span>';
  if (estado === 'pendiente') return '<span class="badge badge-pendiente">Pendiente</span>';
  return '';
}

// ─── Autenticación ───────────────────────────────────────────────────────────
const _ADMIN_PAGES = ['dashboard', 'relojes', 'logs', 'ciclos', 'registros', 'programacion'];

async function initAuth() {
  try {
    const data = await api('GET', '/me/');
    currentUser = data.authenticated ? data : null;
  } catch {
    currentUser = null;
  }
  applyAuthState();
}

function applyAuthState() {
  const isAdmin = currentUser !== null;

  document.querySelectorAll('nav a[data-admin-only]').forEach(el => {
    el.style.display = isAdmin ? '' : 'none';
  });

  const btnLeer = document.getElementById('btn-leer-todos');
  if (btnLeer) btnLeer.style.display = isAdmin ? '' : 'none';

  document.getElementById('auth-guest').style.display = isAdmin ? 'none' : '';
  document.getElementById('auth-user').style.display  = isAdmin ? '' : 'none';
  if (isAdmin) {
    document.getElementById('auth-username-label').textContent = currentUser.username;
  }

  navTo(isAdmin ? 'dashboard' : 'fichadas');

  if (isAdmin && !estadoPollingTimer) {
    estadoPollingTimer = setInterval(fetchEstado, 5000);
  } else if (!isAdmin && estadoPollingTimer) {
    clearInterval(estadoPollingTimer);
    estadoPollingTimer = null;
  }
}

function mostrarLogin() {
  document.getElementById('login-username').value = '';
  document.getElementById('login-password').value = '';
  document.getElementById('login-error').style.display = 'none';
  document.getElementById('modal-login').classList.add('open');
  setTimeout(() => document.getElementById('login-username').focus(), 50);
}

function cerrarLogin() {
  document.getElementById('modal-login').classList.remove('open');
}

async function submitLogin() {
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;
  const errorEl  = document.getElementById('login-error');

  if (!username || !password) {
    errorEl.textContent = 'Ingresá usuario y contraseña';
    errorEl.style.display = '';
    return;
  }

  try {
    const data = await api('POST', '/login/', { username, password });
    currentUser = { authenticated: true, username: data.username };
    cerrarLogin();
    applyAuthState();
    toast(`Bienvenido, ${data.username}`, 'ok');
  } catch (e) {
    errorEl.textContent = e.data?.error || 'Error al iniciar sesión';
    errorEl.style.display = '';
  }
}

async function cerrarSesion() {
  try { await api('POST', '/logout/', {}); } catch {}
  currentUser = null;
  applyAuthState();
  toast('Sesión cerrada', 'ok');
}

// ─── Navegacion ──────────────────────────────────────────────────────────────
function navTo(page) {
  if (!currentUser && _ADMIN_PAGES.includes(page)) page = 'fichadas';
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('nav a').forEach(a => a.classList.remove('active'));
  document.getElementById('page-' + page).classList.add('active');
  document.querySelector(`nav a[data-page="${page}"]`).classList.add('active');
  document.getElementById('topbar-title').textContent = {
    dashboard:     'Dashboard',
    relojes:       'Gestión de Relojes',
    logs:          'Logs de Lectura',
    ciclos:        'Ciclos de Lectura',
    registros:     'Registros en Reloj',
    fichadas:      'Fichadas guardadas',
    programacion:  'Programación',
  }[page];

  if (page === 'dashboard')     renderDashboard();
  if (page === 'relojes')       renderRelojesTable();
  if (page === 'logs')          renderLogsPage();
  if (page === 'ciclos')        renderCiclos();
  if (page === 'registros')     renderRegistros();
  if (page === 'fichadas')      renderFichadas();
  if (page === 'programacion')  renderProgramacion();
}

document.querySelectorAll('nav a[data-page]').forEach(a =>
  a.addEventListener('click', () => navTo(a.dataset.page))
);

// ─── Estado global (polling) ─────────────────────────────────────────────────
async function fetchEstado() {
  try {
    estado = await api('GET', '/estado/');
    updateCicloBanner();
    updateBtnLeer();
  } catch {}
}

function updateCicloBanner() {
  const banner = document.getElementById('ciclo-banner');
  const logBanner = document.getElementById('ciclo-banner-log');
  if (estado.en_progreso && estado.ciclo_activo) {
    const txt = `Ciclo #${estado.ciclo_activo.id} en progreso — ${estado.ciclo_activo.relojes_nombres?.join(', ') || 'cargando...'}`;
    if (banner) {
      banner.classList.add('visible');
      banner.querySelector('.cb-text').textContent = txt;
    }
    if (logBanner) {
      logBanner.classList.add('visible');
      logBanner.querySelector('.cb-text').textContent = txt;
    }
    startLogPolling(estado.ciclo_activo.id);
  } else {
    if (banner) banner.classList.remove('visible');
    if (logBanner) logBanner.classList.remove('visible');
    if (estado.en_progreso === false && logPollingTimer) {
      // Ciclo termino, hacer un fetch final de logs
      setTimeout(() => {
        fetchNuevosLogs();
        renderDashboardIfActive();
        renderRelojesIfActive();
      }, 1200);
    }
  }
}

function renderDashboardIfActive() {
  if (document.getElementById('page-dashboard').classList.contains('active'))
    renderDashboard();
}
function renderRelojesIfActive() {
  if (document.getElementById('page-relojes').classList.contains('active'))
    renderRelojesTable();
}

function updateBtnLeer() {
  document.querySelectorAll('.btn-leer-todos').forEach(btn => {
    btn.disabled = estado.en_progreso;
    btn.innerHTML = estado.en_progreso
      ? '<span class="spinner"></span> Leyendo...'
      : '▶ Leer todos';
  });
}

// ─── Dashboard ───────────────────────────────────────────────────────────────
async function renderDashboard() {
  await fetchEstado();
  const relojes = await api('GET', '/relojes/?page=1&page_size=100').catch(() => ({ results: [] }));
  const lista = relojes.results || relojes;

  const stats = document.getElementById('dash-stats');
  stats.innerHTML = `
    <div class="stat-card">
      <div class="label">Relojes activos</div>
      <div class="value">${estado.relojes_activos ?? '-'}</div>
    </div>
    <div class="stat-card">
      <div class="label">Con error</div>
      <div class="value error">${estado.relojes_con_error ?? '-'}</div>
    </div>
    <div class="stat-card">
      <div class="label">Ultimo ciclo</div>
      <div class="value" style="font-size:16px">${estado.ultimo_ciclo?.inicio_display ?? 'Nunca'}</div>
    </div>
    <div class="stat-card">
      <div class="label">Fichadas (ultimo ciclo)</div>
      <div class="value">${estado.ultimo_ciclo?.total_fichadas ?? '-'}</div>
    </div>
  `;

  const grid = document.getElementById('dash-relojes');
  if (!lista.length) {
    grid.innerHTML = '<p style="color:var(--muted)">No hay relojes registrados.</p>';
    return;
  }
  grid.innerHTML = lista.map(r => {
    const estadoClass = !r.activo ? 'estado-pendiente' : `estado-${r.ultimo_estado}`;
    const enProgreso = estado.en_progreso && estado.ciclo_activo?.relojes?.includes(r.id);
    return `
      <div class="reloj-card ${estadoClass}">
        <div class="rc-header">
          <span class="rc-nombre">${r.nombre}</span>
          ${enProgreso
            ? '<span class="badge badge-progreso">Leyendo</span>'
            : badgeEstado(r.ultimo_estado, r.activo)
          }
        </div>
        <div class="rc-ip">${r.ip}:${r.puerto}</div>
        <div class="rc-info">idadm: ${r.idadm}</div>
        ${r.ultimo_ciclo_display
          ? `<div class="rc-ultimo">Ultimo: ${r.ultimo_ciclo_display}</div>`
          : '<div class="rc-ultimo">Sin lectura</div>'
        }
        ${r.ultimo_estado === 'error' && r.ultimo_error
          ? `<div class="rc-error">${r.ultimo_error}</div>`
          : ''
        }
        <div class="rc-actions">
          <button class="btn btn-ghost btn-sm" onclick="leerReloj(${r.id}, '${r.nombre}')"
            ${!r.activo || estado.en_progreso ? 'disabled' : ''}>
            ▶ Leer
          </button>
          <button class="btn btn-ghost btn-sm" onclick="pingReloj(${r.id}, '${r.nombre}')"
            ${!r.activo ? 'disabled' : ''}>
            ⬡ Ping
          </button>
        </div>
      </div>
    `;
  }).join('');
}

// ─── Ping reloj ───────────────────────────────────────────────────────────────
async function pingReloj(id, nombre) {
  try {
    await api('POST', `/relojes/${id}/ping/`);
    toast(`${nombre}: conectado`, 'ok');
  } catch (e) {
    toast(e.data?.error || `${nombre}: sin respuesta`, 'error');
  }
}

// ─── Reiniciar reloj ─────────────────────────────────────────────────────────
async function reiniciarReloj(id, nombre) {
  if (!confirm(`¿Reiniciar el reloj "${nombre}"?`)) return;
  try {
    await api('POST', `/relojes/${id}/reiniciar/`);
    toast(`Reinicio enviado a ${nombre}`, 'ok');
  } catch (e) {
    toast(e.data?.error || `Error al reiniciar ${nombre}`, 'error');
  }
}

// ─── Leer reloj individual ───────────────────────────────────────────────────
async function leerReloj(id, nombre) {
  try {
    const res = await api('POST', `/relojes/${id}/leer/`);
    toast(`Lectura iniciada para ${nombre} (ciclo #${res.ciclo_id})`, 'info');
    navTo('logs');
    startLogPolling(res.ciclo_id);
    await fetchEstado();
  } catch (e) {
    toast(e.data?.error || 'Error al iniciar lectura', 'error');
  }
}

// ─── Leer todos ───────────────────────────────────────────────────────────────
async function leerTodos() {
  try {
    const res = await api('POST', '/relojes/leer-todos/');
    toast(`Ciclo #${res.ciclo_id} iniciado`, 'info');
    navTo('logs');
    startLogPolling(res.ciclo_id);
    await fetchEstado();
  } catch (e) {
    toast(e.data?.error || 'Error al iniciar ciclo', 'error');
  }
}

// ─── Tabla de relojes ─────────────────────────────────────────────────────────
async function renderRelojesTable() {
  const data = await api('GET', '/relojes/').catch(() => ({ results: [] }));
  const lista = data.results || data;

  const tbody = document.getElementById('relojes-tbody');
  if (!lista.length) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--muted);padding:30px">No hay relojes. Agregue uno con el botón +</td></tr>`;
    return;
  }
  tbody.innerHTML = lista.map(r => `
    <tr>
      <td>${r.nombre}</td>
      <td class="mono">${r.ip}</td>
      <td class="mono">${r.puerto}</td>
      <td class="mono">${r.password}</td>
      <td class="mono">${r.idadm}</td>
      <td>${r.activo
        ? '<span class="chip-on">● Activo</span>'
        : '<span class="chip-off">● Inactivo</span>'}</td>
      <td>${badgeEstado(r.ultimo_estado, r.activo)}</td>
      <td>
        <div class="actions-cell">
          <button class="btn btn-ghost btn-sm" onclick="abrirModalReloj(${r.id})">Editar</button>
          <button class="btn btn-ghost btn-sm" onclick="verRegistrosReloj(${r.id})">Registros</button>
          <button class="btn btn-ghost btn-sm" onclick="pingReloj(${r.id}, '${r.nombre}')"
            ${!r.activo ? 'disabled' : ''}>Ping</button>
          <button class="btn btn-ghost btn-sm" onclick="reiniciarReloj(${r.id}, '${r.nombre}')"
            ${!r.activo ? 'disabled' : ''}>Reiniciar</button>
          <button class="btn btn-danger btn-sm" onclick="eliminarReloj(${r.id}, '${r.nombre}')">Borrar</button>
        </div>
      </td>
    </tr>
  `).join('');
}

// ─── Modal CRUD de reloj ──────────────────────────────────────────────────────
let editId = null;

function abrirModalReloj(id) {
  editId = id || null;
  const modal = document.getElementById('modal-reloj');
  const titulo = document.getElementById('modal-reloj-titulo');
  titulo.textContent = id ? 'Editar reloj' : 'Nuevo reloj';

  // Resetear form
  document.getElementById('f-nombre').value = '';
  document.getElementById('f-ip').value = '';
  document.getElementById('f-puerto').value = '4370';
  document.getElementById('f-password').value = '0';
  document.getElementById('f-idadm').value = '0';
  document.getElementById('f-activo').checked = true;

  if (id) {
    api('GET', `/relojes/${id}/`).then(r => {
      document.getElementById('f-nombre').value   = r.nombre;
      document.getElementById('f-ip').value       = r.ip;
      document.getElementById('f-puerto').value   = r.puerto;
      document.getElementById('f-password').value = r.password;
      document.getElementById('f-idadm').value    = r.idadm;
      document.getElementById('f-activo').checked = r.activo;
    });
  }

  modal.classList.add('open');
}

function cerrarModalReloj() {
  document.getElementById('modal-reloj').classList.remove('open');
}

async function guardarReloj() {
  const body = {
    nombre:   document.getElementById('f-nombre').value.trim(),
    ip:       document.getElementById('f-ip').value.trim(),
    puerto:   parseInt(document.getElementById('f-puerto').value),
    password: parseInt(document.getElementById('f-password').value),
    idadm:    parseInt(document.getElementById('f-idadm').value),
    activo:   document.getElementById('f-activo').checked,
  };

  if (!body.nombre || !body.ip) {
    toast('Nombre e IP son obligatorios', 'error');
    return;
  }

  try {
    if (editId) {
      await api('PATCH', `/relojes/${editId}/`, body);
      toast('Reloj actualizado', 'ok');
    } else {
      await api('POST', '/relojes/', body);
      toast('Reloj creado', 'ok');
    }
    cerrarModalReloj();
    renderRelojesTable();
  } catch (e) {
    const msg = e.data ? JSON.stringify(e.data) : 'Error al guardar';
    toast(msg, 'error');
  }
}

async function eliminarReloj(id, nombre) {
  if (!confirm(`¿Eliminar el reloj "${nombre}"? Esta acción no se puede deshacer.`)) return;
  try {
    await api('DELETE', `/relojes/${id}/`);
    toast(`Reloj "${nombre}" eliminado`, 'ok');
    renderRelojesTable();
  } catch {
    toast('Error al eliminar', 'error');
  }
}

// ─── Logs ─────────────────────────────────────────────────────────────────────
function renderLogsPage() {
  // Poblar select de ciclos
  api('GET', '/ciclos/?limite=50').then(data => {
    const lista = data.results || data;
    const sel = document.getElementById('log-ciclo-select');
    const current = sel.value;
    sel.innerHTML = '<option value="">— Todos —</option>' +
      lista.map(c => `<option value="${c.id}">Ciclo #${c.id} — ${c.inicio_display} (${c.estado})</option>`).join('');
    if (current) sel.value = current;
  });

  // Poblar select de relojes
  api('GET', '/relojes/').then(data => {
    const lista = data.results || data;
    const sel = document.getElementById('log-reloj-select');
    const current = sel.value;
    sel.innerHTML = '<option value="">— Todos —</option>' +
      lista.map(r => `<option value="${r.nombre}">${r.nombre}</option>`).join('');
    if (current) sel.value = current;
  }).catch(() => toast('No se pudo cargar la lista de relojes', 'error'));

  fetchLogs();
}

async function fetchLogs() {
  lastLogId = 0;
  logCicloId  = document.getElementById('log-ciclo-select').value  || null;
  logRelojFiltro = document.getElementById('log-reloj-select').value || '';
  document.getElementById('log-body').innerHTML = '';
  await fetchNuevosLogs();
}

function _crearFilaLog(l) {
  const row = document.createElement('div');
  row.className = 'log-row' + (l.advertencia ? ' warn' : '');
  row.innerHTML = `
    <span class="log-cell">${l.timestamp_display}</span>
    <span class="log-cell reloj">${l.reloj_nombre}</span>
    <span class="log-cell oper">${l.operacion}</span>
    <span class="log-cell det">${l.detalle}</span>
  `;
  return row;
}

async function fetchNuevosLogs() {
  const isInitial = lastLogId === 0;
  const params = new URLSearchParams();
  if (logCicloId)    params.set('ciclo', logCicloId);
  if (lastLogId)     params.set('after_id', lastLogId);
  if (logRelojFiltro) params.set('reloj', logRelojFiltro);
  params.set('page_size', '200');

  const data = await api('GET', `/logs/?${params}`).catch(() => null);
  if (!data) return;
  const logs = data.results || data;
  if (!logs.length) return;

  // logs llegan en orden -id (más reciente primero)
  logs.forEach(l => { lastLogId = Math.max(lastLogId, l.id); });

  const body = document.getElementById('log-body');

  if (isInitial) {
    // Carga inicial: el API ya trae orden descendente, agregar tal cual
    logs.forEach(l => body.appendChild(_crearFilaLog(l)));
    if (autoScroll) body.parentElement.scrollTop = 0;
  } else {
    // Polling: nuevas entradas van arriba del todo
    const fragment = document.createDocumentFragment();
    logs.forEach(l => fragment.appendChild(_crearFilaLog(l)));
    body.insertBefore(fragment, body.firstChild);
    if (autoScroll) body.parentElement.scrollTop = 0;
  }
}

function startLogPolling(cicloId) {
  if (logPollingTimer) return;
  if (document.getElementById('page-logs').classList.contains('active')) {
    if (cicloId && !logCicloId) {
      logCicloId = String(cicloId);
    }
  }
  logPollingTimer = setInterval(async () => {
    if (document.getElementById('page-logs').classList.contains('active')) {
      await fetchNuevosLogs();
    }
    await fetchEstado();
    if (!estado.en_progreso) {
      clearInterval(logPollingTimer);
      logPollingTimer = null;
      await fetchNuevosLogs();
      renderDashboardIfActive();
      renderRelojesIfActive();
    }
  }, 2000);
}

// ─── Ciclos ───────────────────────────────────────────────────────────────────
async function renderCiclos() {
  const data = await api('GET', '/ciclos/').catch(() => ({ results: [] }));
  const lista = data.results || data;
  const tbody = document.getElementById('ciclos-tbody');

  if (!lista.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:30px">No hay ciclos registrados.</td></tr>`;
    return;
  }

  const badge = e => ({
    exitoso: '<span class="badge badge-ok">Exitoso</span>',
    error:   '<span class="badge badge-error">Error</span>',
    en_progreso: '<span class="badge badge-progreso">En progreso</span>',
  }[e] || e);

  tbody.innerHTML = lista.map(c => `
    <tr>
      <td>#${c.id}</td>
      <td>${c.inicio_display}</td>
      <td>${c.fin_display || '—'}</td>
      <td>${badge(c.estado)}</td>
      <td>${c.total_fichadas}</td>
      <td>${c.relojes_nombres?.join(', ') || '—'}</td>
    </tr>
  `).join('');
}

// ─── Registros en reloj ───────────────────────────────────────────────────────
let _registrosPreselect = null;

function verRegistrosReloj(id) {
  _registrosPreselect = id;
  navTo('registros');
}

async function renderRegistros() {
  const data = await api('GET', '/relojes/').catch(() => ({ results: [] }));
  const lista = (data.results || data).filter(r => r.activo);
  const sel = document.getElementById('reg-reloj-select');
  sel.innerHTML = '<option value="">— Seleccione un reloj —</option>' +
    lista.map(r => `<option value="${r.id}">${r.nombre} (${r.ip})</option>`).join('');

  if (_registrosPreselect) {
    sel.value = String(_registrosPreselect);
    _registrosPreselect = null;
    await cargarRegistros();
  }
}

async function cargarRegistros() {
  const sel = document.getElementById('reg-reloj-select');
  const id = sel.value;
  if (!id) { toast('Seleccione un reloj', 'error'); return; }

  const nombre = sel.options[sel.selectedIndex].text;
  const btn = document.getElementById('reg-cargar-btn');
  const statusEl = document.getElementById('reg-status');
  const tbody = document.getElementById('reg-tbody');

  btn.disabled = true;
  btn.textContent = 'Cargando...';
  statusEl.textContent = `Conectando a ${nombre}...`;
  tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--muted);padding:30px">Leyendo registros del reloj...</td></tr>`;

  try {
    const data = await api('GET', `/relojes/${id}/registros/`);
    statusEl.textContent = `${data.total} registros`;

    if (!data.registros.length) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--muted);padding:30px">El reloj no tiene registros almacenados.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.registros.map(r => `
      <tr>
        <td class="mono">${r.user_id}</td>
        <td>${r.nombre || '—'}</td>
        <td class="mono">${r.timestamp}</td>
        <td>${r.tipo}</td>
      </tr>
    `).join('');
  } catch (e) {
    statusEl.textContent = '';
    toast(e.data?.error || `Error al leer ${nombre}`, 'error');
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--muted);padding:30px">No se pudo conectar al reloj.</td></tr>`;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Cargar';
  }
}

// ─── Fichadas guardadas ───────────────────────────────────────────────────────
let _fichadasData    = [];
let _fichadasSortCol = 'hora';
let _fichadasSortDir = -1;  // -1 desc, 1 asc

async function renderFichadas() {
  await buscarFichadas();
}

async function buscarFichadas() {
  const reloj  = document.getElementById('fich-reloj').value;
  const legajo = document.getElementById('fich-legajo').value.trim();
  const nombre = document.getElementById('fich-nombre').value.trim();
  const desde  = document.getElementById('fich-desde').value;
  const hasta  = document.getElementById('fich-hasta').value;
  const tbody    = document.getElementById('fich-tbody');
  const statusEl = document.getElementById('fich-status');

  tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:30px">Buscando...</td></tr>`;
  statusEl.textContent = '';

  const params = new URLSearchParams();
  if (reloj)  params.set('reloj', reloj);
  if (legajo) params.set('legajo', legajo);
  if (nombre) params.set('nombre', nombre);
  if (desde)  params.set('fecha_desde', desde);
  if (hasta)  params.set('fecha_hasta', hasta);

  try {
    const data = await api('GET', `/fichadas/?${params}`);

    // Actualizar dropdown de relojes conservando selección
    const selReloj = document.getElementById('fich-reloj');
    const currentReloj = selReloj.value;
    selReloj.innerHTML = '<option value="">— Todos —</option>' +
      (data.relojes_disponibles || []).map(r => `<option value="${r}">${r}</option>`).join('');
    selReloj.value = currentReloj;

    statusEl.textContent = data.total > data.mostrados
      ? `Mostrando ${data.mostrados} de ${data.total} — use filtros para acotar`
      : `${data.total} registros`;

    _fichadasData = data.registros;
    _renderFichadasTable();
  } catch (e) {
    statusEl.textContent = '';
    toast(e.data?.error || 'Error al cargar fichadas', 'error');
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:30px">Error al cargar.</td></tr>`;
  }
}

function _renderFichadasTable() {
  const tbody = document.getElementById('fich-tbody');

  if (!_fichadasData.length) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:30px">Sin registros para los filtros seleccionados.</td></tr>`;
    return;
  }

  const sorted = [..._fichadasData].sort((a, b) => {
    const va = a[_fichadasSortCol] || '';
    const vb = b[_fichadasSortCol] || '';
    return va < vb ? -_fichadasSortDir : va > vb ? _fichadasSortDir : 0;
  });

  tbody.innerHTML = sorted.map(r => `
    <tr>
      <td class="mono">${r.legajo}</td>
      <td>${r.nombre || '—'}</td>
      <td class="mono">${r.hora}</td>
      <td>${r.tipo}</td>
      <td>${r.reloj}</td>
    </tr>
  `).join('');

  ['legajo', 'nombre', 'hora'].forEach(col => {
    const el = document.getElementById(`sort-${col}`);
    if (!el) return;
    if (col === _fichadasSortCol) {
      el.textContent = _fichadasSortDir === 1 ? '▲' : '▼';
      el.style.color = 'var(--primary)';
    } else {
      el.textContent = '⇅';
      el.style.color = 'var(--muted)';
    }
  });
}

function sortFichadas(col) {
  if (_fichadasSortCol === col) {
    _fichadasSortDir *= -1;
  } else {
    _fichadasSortCol = col;
    _fichadasSortDir = col === 'hora' ? -1 : 1;
  }
  _renderFichadasTable();
}

function limpiarFiltrosFichadas() {
  document.getElementById('fich-reloj').value  = '';
  document.getElementById('fich-legajo').value = '';
  document.getElementById('fich-nombre').value = '';
  document.getElementById('fich-desde').value  = '';
  document.getElementById('fich-hasta').value  = '';
  buscarFichadas();
}

// ─── Programación ─────────────────────────────────────────────────────────────
let _tareaEditId = null;

async function renderProgramacion() {
  const data = await api('GET', '/tareas/').catch(() => ({ results: [] }));
  const lista = data.results || data;

  const countEl = document.getElementById('prog-count');
  if (countEl) countEl.textContent = lista.length ? lista.length : '';

  const tbody = document.getElementById('prog-tbody');
  if (!lista.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:30px">No hay tareas programadas. Cree una con "+ Nueva tarea".</td></tr>`;
    return;
  }

  tbody.innerHTML = lista.map(t => {
    const relojesText = t.relojes_nombres && t.relojes_nombres.length
      ? t.relojes_nombres.join(', ')
      : '—';
    const estadoBadge = t.activo
      ? '<span class="badge badge-ok">Activa</span>'
      : '<span class="badge badge-inactivo">Pausada</span>';
    const dot = t.activo
      ? '<span style="color:var(--success);font-size:10px">●</span>'
      : '<span style="color:var(--muted);font-size:10px">●</span>';
    const toggleBtn = t.activo
      ? `<button class="btn btn-ghost btn-sm" onclick="toggleTarea(${t.id})" title="Pausar">⏸</button>`
      : `<button class="btn btn-ghost btn-sm" onclick="toggleTarea(${t.id})" title="Activar">▶</button>`;
    return `
      <tr>
        <td>${dot}</td>
        <td style="font-weight:600">${t.nombre}</td>
        <td class="mono" style="color:var(--primary)">${t.expresion_cron}</td>
        <td>${relojesText}</td>
        <td class="mono">${t.proxima_ejecucion_display || '—'}</td>
        <td>${estadoBadge}</td>
        <td>
          <div class="actions-cell">
            ${toggleBtn}
            <button class="btn btn-ghost btn-sm" onclick="abrirModalTarea(${t.id})">✎ Editar</button>
            <button class="btn btn-danger btn-sm" onclick="eliminarTarea(${t.id}, '${t.nombre.replace(/'/g, "\\'")}')">✕</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function abrirModalTarea(id) {
  _tareaEditId = id || null;
  document.getElementById('modal-tarea-titulo').textContent = id ? 'Editar tarea' : 'Nueva tarea';
  document.getElementById('tp-nombre').value = '';
  document.getElementById('tp-cron').value = '';
  document.getElementById('tp-activo').checked = true;

  api('GET', '/relojes/').then(data => {
    const lista = data.results || data;
    const container = document.getElementById('tp-relojes-list');
    if (!lista.length) {
      container.innerHTML = '<span style="color:var(--muted);font-size:12px">No hay relojes registrados</span>';
    } else {
      container.innerHTML = lista.map(r => `
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:13px">
          <input type="checkbox" class="tp-reloj-cb" value="${r.id}" style="accent-color:var(--primary)">
          <span>${r.nombre}</span>
          <span style="color:var(--muted);font-size:11px">${r.ip}</span>
        </label>
      `).join('');
    }

    if (id) {
      api('GET', `/tareas/${id}/`).then(t => {
        document.getElementById('tp-nombre').value   = t.nombre;
        document.getElementById('tp-cron').value     = t.expresion_cron;
        document.getElementById('tp-activo').checked = t.activo;
        document.querySelectorAll('.tp-reloj-cb').forEach(cb => {
          cb.checked = t.relojes.includes(parseInt(cb.value));
        });
      });
    }
  }).catch(() => {
    document.getElementById('tp-relojes-list').innerHTML =
      '<span style="color:var(--muted);font-size:12px">Error al cargar relojes</span>';
  });

  document.getElementById('modal-tarea').classList.add('open');
}

function cerrarModalTarea() {
  document.getElementById('modal-tarea').classList.remove('open');
}

async function guardarTarea() {
  const nombre = document.getElementById('tp-nombre').value.trim();
  const cron   = document.getElementById('tp-cron').value.trim();
  const activo = document.getElementById('tp-activo').checked;
  const relojes = Array.from(document.querySelectorAll('.tp-reloj-cb:checked'))
    .map(cb => parseInt(cb.value));

  if (!nombre) { toast('El nombre es obligatorio', 'error'); return; }
  if (!cron)   { toast('La expresión CRON es obligatoria', 'error'); return; }

  try {
    if (_tareaEditId) {
      await api('PATCH', `/tareas/${_tareaEditId}/`, { nombre, expresion_cron: cron, activo, relojes });
      toast('Tarea actualizada', 'ok');
    } else {
      await api('POST', '/tareas/', { nombre, expresion_cron: cron, activo, relojes });
      toast('Tarea creada', 'ok');
    }
    cerrarModalTarea();
    renderProgramacion();
  } catch (e) {
    const msg = e.data ? JSON.stringify(e.data) : 'Error al guardar';
    toast(msg, 'error');
  }
}

async function toggleTarea(id) {
  try {
    const res = await api('POST', `/tareas/${id}/toggle/`);
    toast(res.activo ? 'Tarea activada' : 'Tarea pausada', 'ok');
    renderProgramacion();
  } catch {
    toast('Error al cambiar estado', 'error');
  }
}

async function eliminarTarea(id, nombre) {
  if (!confirm(`¿Eliminar la tarea "${nombre}"? Esta acción no se puede deshacer.`)) return;
  try {
    await api('DELETE', `/tareas/${id}/`);
    toast(`Tarea "${nombre}" eliminada`, 'ok');
    renderProgramacion();
  } catch {
    toast('Error al eliminar tarea', 'error');
  }
}

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initAuth();
});
