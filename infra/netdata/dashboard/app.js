/* Static view, using the existing local Netdata API. No external dependencies. */
const GiB = 1024 ** 3;
const number = (n, digits = 1) => Number(n).toLocaleString('es-AR', {maximumFractionDigits: digits});
const clock = t => new Date(t * 1000).toLocaleTimeString('es-AR', {hour:'2-digit', minute:'2-digit'});

function sum(values) {
  const valid = values.filter(v => typeof v === 'number' && Number.isFinite(v));
  return valid.length ? valid.reduce((a, b) => a + b, 0) : null;
}
function metric(data, kind) {
  const names = data.dimension_names;
  const select = values => kind === 'cpu' ? sum(values) : values[names.indexOf(kind === 'host-ram' ? 'used' : 'ram')];
  const scale = kind === 'cpu' ? 1 : 1 / 1024; // Netdata RAM is MiB.
  const convert = values => {const v = select(values); return typeof v === 'number' && Number.isFinite(v) ? v * scale : null;};
  return {current: convert(data.latest_values),
    points: data.result.data.map(row => [row[0], convert(row.slice(1))]).sort((a,b) => a[0]-b[0]),
    total: kind === 'host-ram' ? sum(data.latest_values) / 1024 : null,
    last: data.last_entry, after: data.after, before: data.before};
}

function element(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}
function sparkline(parent, series, maximum, color) {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', '0 0 360 100'); svg.setAttribute('class', 'chart');
  svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', 'Historial de uso');
  const path = (d, stroke, width) => {
    const p = document.createElementNS(ns, 'path');
    p.setAttribute('d', d); p.setAttribute('fill', 'none');
    p.setAttribute('stroke', stroke); p.setAttribute('stroke-width', width);
    p.setAttribute('vector-effect', 'non-scaling-stroke'); svg.append(p);
  };
  [4,48,92].forEach(y => path(`M0,${y}H360`, '#303c4f', 1));
  const ceiling = Math.max(maximum || 0, ...series.points.map(p => p[1] || 0), 0.1);
  const duration = Math.max(1, series.before-series.after);
  let d = '', gap = true;
  series.points.forEach(([time, value]) => {
    if (value === null) {gap = true; return;}
    const x = 360*(time-series.after)/duration, y = 92-88*value/ceiling;
    d += `${gap ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`; gap = false;
  });
  path(d, color, 2); parent.append(svg);
  const axis = element('div', 'axis');
  axis.append(element('span', '', clock(series.after)), element('span', '', `${number(ceiling)} máx. · ${clock(series.before)}`));
  parent.append(axis);
}
async function json(url) {
  const r = await fetch(url, {cache:'no-store', signal:AbortSignal.timeout(10000)});
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
async function chart(id, kind, range) {
  const query = new URLSearchParams({chart:id, after:-range, points:120, options:'jsonwrap'});
  return metric(await json(`/api/v1/data?${query}`), kind);
}
async function historyCard(title, id, kind, range, note, running, limit) {
  const card = element('article', 'card'); card.append(element('h4', '', title));
  if (!running) {card.append(element('div', 'value', '—'), element('p', 'note', 'Entorno detenido')); return card;}
  try {
    const s = await chart(id, kind, range);
    const fresh = Date.now()/1000-s.last < 45;
    card.append(element('div', 'value', fresh && s.current !== null ? `${number(s.current)} ${kind === 'cpu' ? '%' : 'GiB'}` : '—'));
    card.append(element('p', `note${fresh ? '' : ' error'}`, fresh ? note(s) : 'Sin muestras recientes'));
    sparkline(card, s, kind === 'cpu' ? limit : s.total, kind === 'cpu' ? '#77cabc' : '#91b9e6');
  } catch {card.append(element('p', 'note error', 'Métrica no disponible'));}
  return card;
}
function diskCard(item, filesystems, updated, interval) {
  const card = element('article', 'card'); card.append(element('h4', '', 'Disco'));
  const stale = Date.now()/1000-(item ? item.measured_at || 0 : updated) > interval*1.8;
  const entries = item ? [item] : filesystems;
  for (const f of entries) {
    if (f.used_bytes === undefined) {card.append(element('div', 'value', '—')); continue;}
    card.append(element('div', 'value', `${number(f.used_bytes/GiB)} GiB`));
    card.append(element('p', 'note', item ? 'Ocupados por este entorno' : `Usados en ${f.path}`));
    if (f.total_bytes) {
      const bar = element('div', 'bar'), fill = element('span');
      fill.style.width = `${Math.min(100, f.used_bytes/f.total_bytes*100)}%`; bar.append(fill); card.append(bar);
      card.append(element('div', 'disk-extra', `${number(f.available_bytes/GiB)} GiB disponibles · ${number(f.total_bytes/GiB)} GiB totales`));
      if (f.reserved_bytes) card.append(element('div', 'note', `${number(f.reserved_bytes/GiB)} GiB reservados por el sistema`));
    }
  }
  card.append(element('p', `note${stale || item?.error ? ' error' : ''}`,
    item?.error ? 'Falló el último barrido · se conserva la medición anterior' : stale ? 'Medición de disco desactualizada' : `Medido ${clock(item ? item.measured_at : updated)}`));
  if (item) card.append(element('p', 'note', 'Espacio libre compartido con el host'));
  return card;
}
async function section(name, item, snapshot, range) {
  const running = !item || item.status === 'Running';
  const section = element('section', 'section'), heading = element('div', 'section-title');
  heading.append(element('h3', '', name));
  if (item) heading.append(element('span', `badge${running ? ' running' : ''}`, running ? 'En ejecución' : 'Detenido'));
  section.append(heading);
  const prefix = item ? `cgroup_${item.name}` : 'system';
  const limits = item?.cpu_limit && /^\d+$/.test(item.cpu_limit) ? Number(item.cpu_limit) : null;
  const [cpu, ram] = await Promise.all([
    historyCard('CPU', `${prefix}.cpu`, 'cpu', range,
      () => item ? `100% = 1 núcleo${limits ? ` · límite ${limits} núcleos` : ''}` : `Total del host · ${snapshot.cpu_cores} núcleos`, running, item ? (limits || 1)*100 : 100),
    historyCard('RAM', item ? `${prefix}.mem_usage` : 'system.ram', item ? 'ram' : 'host-ram', range,
      s => item ? `RAM en uso${item.memory_limit ? ` · límite ${item.memory_limit}` : ''}` : `${number(s.total)} GiB totales · caché disponible excluida del uso`, running)
  ]);
  const cards = element('div', 'cards'); cards.append(cpu, ram, diskCard(item, snapshot.filesystems, snapshot.updated_at, snapshot.interval_seconds));
  section.append(cards); return section;
}
let busy = false;
async function refresh() {
  if (busy || document.hidden) return;
  busy = true;
  try {
    const range = Number(document.getElementById('range').value);
    const snapshot = await json('incus-storage.json');
    document.getElementById('hostname').textContent = snapshot.hostname || 'Homelab';
    const sections = await Promise.all([section('Servidor', null, snapshot, range),
      ...snapshot.instances.map(item => section(item.name, item, snapshot, range))]);
    document.getElementById('hosts').replaceChildren(sections[0]);
    document.getElementById('instances').replaceChildren(...sections.slice(1));
    const status = document.getElementById('status'); status.className = '';
    status.textContent = `Vista actualizada ${clock(Date.now()/1000)} · ${snapshot.instances.length} entornos`;
  } catch {
    const status = document.getElementById('status'); status.className = 'error';
    status.textContent = 'No se pudo actualizar. Se conserva la vista anterior.';
  } finally {busy = false;}
}
if (typeof document !== 'undefined') {
  document.getElementById('range').addEventListener('change', refresh);
  document.addEventListener('visibilitychange', refresh);
  refresh(); setInterval(refresh, 15000);
}
if (typeof module !== 'undefined') module.exports = {metric, sum};
