/* One local Netdata API, one hour of history. No dependencies or background service. */
const GiB = 1024 ** 3;
const HOUR = 3600;
const number = (n, digits = 1) => Number(n).toLocaleString('en-US', {maximumFractionDigits: digits});
const clock = t => new Date(t * 1000).toLocaleTimeString('en-GB', {hour:'2-digit', minute:'2-digit'});
const valid = n => typeof n === 'number' && Number.isFinite(n);
const memory = gib => gib < 1 ? [number(gib * 1024, 0), 'MiB'] : [number(gib), 'GiB'];

function sum(values) {
  const valuesWithData = values.filter(valid);
  return valuesWithData.length ? valuesWithData.reduce((a, b) => a + b, 0) : null;
}
function metric(data, kind) {
  const names = data.dimension_names;
  const dimension = kind === 'host-ram' ? 'used' : kind === 'available' ? 'avail' : 'ram';
  const select = values => kind === 'cpu' ? sum(values) : values[names.indexOf(dimension)];
  const scale = kind === 'cpu' ? 1 : 1 / 1024;
  const convert = values => {const value = select(values); return valid(value) ? value * scale : null;};
  const total = data.latest_values.every(valid) ? sum(data.latest_values) : null;
  return {current: convert(data.latest_values),
    points: data.result.data.map(row => [row[0], convert(row.slice(1))]).sort((a,b) => a[0]-b[0]),
    total: kind === 'host-ram' && total !== null ? total / 1024 : null,
    last: data.last_entry, after: data.after, before: data.before};
}
function hostMemory(ram, available) {
  if (!ram || !available || !valid(ram.total) || ram.total <= 0) return null;
  const usable = value => valid(value) && value >= 0 && value <= ram.total;
  const used = value => usable(value) ? ram.total-value : null;
  return {...available, current:used(available.current),
    points:available.points.map(([time,value]) => [time,used(value)]),
    available:usable(available.current) ? available.current : null,
    total:ram.total, last:Math.min(ram.last, available.last)};
}
function limitCaption(raw) {
  if (raw === null || raw === undefined || raw === '') return 'No limit';
  if (/^\d+(?:\.\d+)?%$/.test(raw)) return `Limit: ${raw} of host`;
  const match = String(raw).match(/^(\d+(?:\.\d+)?)\s*(B|[KMGT]i?B)?$/i);
  if (!match) return 'Limit unavailable';
  const units = {B:1,KB:1e3,MB:1e6,GB:1e9,TB:1e12,KIB:1024,MIB:1024**2,GIB:GiB,TIB:1024**4};
  const bytes = Number(match[1])*units[(match[2] || 'B').toUpperCase()];
  return bytes > 0 ? `of ${memory(bytes/GiB).join(' ')}` : 'Limit unavailable';
}
function cpuShare(series, cores) {
  if (!series || !valid(cores) || cores <= 0) return null;
  return {...series, current: valid(series.current) ? series.current / cores : null,
    points: series.points.map(([time, value]) => [time, valid(value) ? value / cores : null])};
}
function storageOrder(instances) {
  return [...instances].sort((a,b) => (b.used_bytes ?? -1)-(a.used_bytes ?? -1) || a.name.localeCompare(b.name));
}
function ceiling(series, minimum) {
  const peak = Math.max(minimum, ...series.filter(Boolean).flatMap(s => [s.current || 0, ...s.points.map(p => p[1] || 0)]));
  const base = 10 ** Math.floor(Math.log10(peak));
  return [1,2,5,10].map(n => n * base).find(n => n >= peak) || peak;
}
function ageText(timestamp, now = Date.now()/1000) {
  const minutes = Math.max(0, Math.floor((now-timestamp)/60));
  if (minutes < 1) return 'now';
  if (minutes < 60) return `${minutes}m ago`;
  if (minutes < 1440) return `${Math.floor(minutes/60)}h ago`;
  return `${Math.floor(minutes/1440)}d ago`;
}
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function svgElement(tag, attrs) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
  return node;
}
function valueNode(value, unit = '') {
  const node = element('div', 'metric-value', value);
  if (unit) node.append(element('span', 'metric-unit', unit));
  return node;
}
function rowIcon(host) {
  const box = element('span', 'row-icon');
  box.setAttribute('aria-hidden', 'true');
  const svg = svgElement('svg', {viewBox:'0 0 24 24'});
  svg.append(svgElement('path', {d:host ? 'M4 4h16v6H4zM4 14h16v6H4zM7 7h1m-1 10h1' : 'M12 3 3 8l9 5 9-5-9-5ZM3 8v9l9 5 9-5V8M12 13v9'}));
  box.append(svg); return box;
}
let plotId = 0;
function drawPlot(parent, series, max, kind, label, muted) {
  const id = `plot-${++plotId}`;
  const wrapper = element('div', 'plot');
  wrapper.tabIndex = 0; wrapper.setAttribute('role', 'img');
  wrapper.setAttribute('aria-label', `${label}, last hour. Arrow keys navigate samples.`);
  const color = kind === 'cpu' ? 'var(--cpu)' : 'var(--ram)';
  const svg = svgElement('svg', {viewBox:'0 0 420 112', preserveAspectRatio:'none', class:'chart', 'aria-hidden':'true'});
  if (muted) svg.style.opacity = '.35';
  const defs = svgElement('defs', {}), gradient = svgElement('linearGradient', {id, x1:'0',y1:'0',x2:'0',y2:'1'});
  gradient.append(svgElement('stop', {offset:'0%', 'stop-color':color, 'stop-opacity':'.24'}),
    svgElement('stop', {offset:'100%', 'stop-color':color, 'stop-opacity':'.015'}));
  defs.append(gradient); svg.append(defs);
  svg.append(svgElement('path', {d:'M0 108H420 M0 57H420', class:'chart-grid'}));
  const x = time => Math.max(0, Math.min(420, 420*(time-series.after)/Math.max(1, series.before-series.after)));
  const y = value => 108-98*Math.max(0,Math.min(max,value))/max;
  let segments = [], segment = [];
  for (const [time, value] of series.points) {
    if (value === null) {if (segment.length) segments.push(segment); segment = [];}
    else segment.push([x(time), y(value)]);
  }
  if (segment.length) segments.push(segment);
  for (const points of segments) {
    const line = points.map(([px,py], i) => `${i ? 'L' : 'M'}${px.toFixed(2)},${py.toFixed(2)}`).join('');
    const area = `${line}L${points.at(-1)[0]},108L${points[0][0]},108Z`;
    svg.append(svgElement('path', {d:area, fill:`url(#${id})`}));
    svg.append(svgElement('path', {d:line, fill:'none', stroke:color, 'stroke-width':'2', 'vector-effect':'non-scaling-stroke', 'stroke-linejoin':'round', 'stroke-linecap':'round'}));
  }
  wrapper.append(svg, element('span', 'plot-ceiling', `${number(max)}${kind === 'cpu' ? '%' : ' GiB'}`));
  const tooltip = element('output', 'plot-tooltip'), cursor = element('span', 'plot-cursor');
  tooltip.hidden = cursor.hidden = true; wrapper.append(cursor, tooltip);
  const samples = series.points.filter(p => p[1] !== null);
  let index = samples.length-1;
  const show = () => {
    if (!samples[index]) return;
    const [time,value] = samples[index];
    const position = x(time)/420*wrapper.clientWidth;
    cursor.style.left = `${position}px`;
    tooltip.style.left = `${Math.max(70, Math.min(wrapper.clientWidth-70, position))}px`;
    tooltip.textContent = `${clock(time)} · ${kind === 'cpu' ? number(value)+'%' : memory(value).join(' ')}`;
    tooltip.hidden = cursor.hidden = false;
  };
  wrapper.addEventListener('pointermove', event => {
    const bounds = wrapper.getBoundingClientRect();
    const time = series.after+(event.clientX-bounds.left)/bounds.width*(series.before-series.after);
    index = samples.reduce((best,p,i) => Math.abs(p[0]-time)<Math.abs(samples[best][0]-time) ? i : best, 0);
    show();
  });
  const hide = () => {tooltip.hidden = cursor.hidden = true;};
  wrapper.addEventListener('pointerleave', hide);
  wrapper.addEventListener('blur', hide);
  wrapper.addEventListener('focus', show);
  wrapper.addEventListener('keydown', event => {
    if (event.key === 'Escape') hide();
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault(); index = Math.max(0, Math.min(samples.length-1, index+(event.key === 'ArrowLeft' ? -1 : 1))); show();
  });
  parent.append(wrapper);
  const axis = element('div', 'time-axis');
  axis.append(element('span', '', '−1h'), element('span', '', 'now')); parent.append(axis);
}
function historyBlock(label, series, kind, max, running, detail = '', description = '') {
  const block = element('div', 'metric'), heading = element('div', 'metric-heading');
  const fresh = running && series && Date.now()/1000-series.last < 45;
  const name = element('span', 'metric-name', label); name.title = description;
  heading.append(name);
  heading.append(fresh && valid(series.current) ? valueNode(...(kind === 'cpu' ? [number(series.current),'%'] : memory(series.current))) : valueNode('—'));
  block.append(heading);
  block.append(element('div', 'metric-detail', typeof detail === 'function' ? detail(fresh) : detail));
  if (series?.points.some(p => p[1] !== null)) drawPlot(block, series, max, kind, label, !fresh);
  else block.append(element('div', 'no-data', running ? 'No data' : 'Stopped'));
  return block;
}
function diskBlock(item, snapshot) {
  const block = element('div', 'metric disk'); block.append(element('span', 'metric-name', 'STORAGE'));
  const fs = item || snapshot.filesystems.find(f => f.path === '/') || snapshot.filesystems[0];
  block.append(fs && valid(fs.used_bytes) ? valueNode(number(fs.used_bytes/GiB), 'GiB') : valueNode('—'));
  if (!item && fs && valid(fs.available_bytes)) block.append(element('div', 'disk-free', `${number(fs.available_bytes/GiB,0)} GiB available`));
  const measured = item ? item.measured_at : snapshot.updated_at;
  const stale = !measured || Date.now()/1000-measured > snapshot.interval_seconds*1.8;
  const caption = item?.error ? 'Last reading · scan failed' : stale ? `Stale${measured ? ' · '+ageText(measured) : ''}` : '';
  const note = element('div', `disk-caption${item?.error || (stale && item?.status === 'Running') ? ' issue' : ''}`, caption);
  if (measured) note.title = `Measured ${clock(measured)}`;
  block.append(note); return block;
}
function resourceRow(record, snapshot, scales) {
  const host = !record.item, running = host || record.item.status === 'Running';
  const row = element('article', `resource-row${host ? ' host-row' : ''}`);
  const heading = element('div', 'row-heading'), identity = element('div', 'row-identity');
  const title = element('h3', '', host ? 'Host' : record.item.name.replace(/^dev-/,''));
  if (!host) title.title = record.item.name;
  identity.append(rowIcon(host), title); heading.append(identity);
  heading.append(element('span', `state${running ? ' running' : ''}`, running ? (host ? 'Online' : 'Running') : 'Stopped'));
  row.append(heading);
  const metrics = element('div', 'metrics');
  const ramDetail = host ? fresh => fresh && valid(record.ram?.available) ? `${memory(record.ram.available).join(' ')} available` : 'Available: —' : limitCaption(record.item.memory_limit);
  const ramDescription = host ? 'Estimated used memory: total minus available' : 'Working set: usage minus inactive file cache';
  metrics.append(historyBlock('CPU', record.cpu, 'cpu', scales.cpu, running, '', 'Percent of total host CPU'),
    historyBlock('RAM', record.ram, 'ram', scales.ram, running, ramDetail, ramDescription), diskBlock(record.item, snapshot));
  row.append(metrics); return row;
}
async function json(url) {
  const response = await fetch(url, {cache:'no-store', signal:AbortSignal.timeout(10000)});
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}
let apiPrefixPromise;
function apiPrefix() {
  if (!apiPrefixPromise) {
    apiPrefixPromise = (async () => {
      try {await json('api/v1/info'); return 'api/v1';}
      catch {await json('/api/v1/info'); return '/api/v1';}
    })().catch(error => {apiPrefixPromise = undefined; throw error;});
  }
  return apiPrefixPromise;
}
async function history(id, kind, before) {
  try {
    const query = new URLSearchParams({chart:id, after:before-HOUR, before, points:180, options:'jsonwrap'});
    const prefix = await apiPrefix();
    return metric(await json(`${prefix}/data?${query}`), kind);
  } catch {return null;}
}
async function readRow(item, cores, before) {
  const prefix = item ? `cgroup_${item.name}` : 'system';
  const [cpu,ram,available] = await Promise.all([
    history(`${prefix}.cpu`, 'cpu', before),
    history(item ? `${prefix}.mem_usage` : 'system.ram', item ? 'ram' : 'host-ram', before),
    item ? Promise.resolve(null) : history('mem.available', 'available', before)
  ]);
  return {item, cpu:item ? cpuShare(cpu, cores) : cpu, ram:item ? ram : hostMemory(ram, available)};
}
let busy = false;
async function refresh() {
  if (busy || document.hidden) return;
  busy = true;
  const status = document.getElementById('status');
  try {
    const snapshot = await json('incus-storage.json');
    const before = Math.floor(Date.now()/1000);
    const records = await Promise.all([readRow(null, snapshot.cpu_cores, before), ...storageOrder(snapshot.instances).map(item => readRow(item, snapshot.cpu_cores, before))]);
    const scales = {cpu:ceiling(records.map(r => r.cpu), 10), ram:ceiling(records.map(r => r.ram), .5)};
    const rows = records.map(record => resourceRow(record, snapshot, scales));
    const host = document.getElementById('host'); host.replaceChildren(rows[0]); host.setAttribute('aria-busy', 'false');
    document.getElementById('instances').replaceChildren(...rows.slice(1));
    if (!snapshot.instances.length) document.getElementById('instances').append(element('div', 'empty-state', 'No containers'));
    document.getElementById('count').textContent = snapshot.instances.length;
    document.getElementById('hostname').textContent = snapshot.hostname || 'Homelab';
    document.title = `Resources · ${snapshot.hostname || 'Homelab'}`;
    const readings = records.filter(r => !r.item || r.item.status === 'Running').flatMap(r => [r.cpu,r.ram]);
    const live = readings.every(s => s && Date.now()/1000-s.last < 45 && valid(s.current));
    status.className = `live-status ${live ? 'live' : 'issue'}`;
    status.textContent = live ? 'Live' : 'Pending data';
    status.title = `Updated ${clock(Date.now()/1000)}`;
    const diskAge = Date.now()/1000-snapshot.updated_at;
    document.getElementById('disk-updated').textContent = diskAge > snapshot.interval_seconds*1.8 ? `Disk: stale · ${ageText(snapshot.updated_at)}` : `Disk: ${ageText(snapshot.updated_at)}`;
  } catch {
    status.className = 'live-status issue'; status.textContent = 'Offline';
    const host = document.getElementById('host');
    if (host.getAttribute('aria-busy') === 'true') {
      host.replaceChildren(element('div', 'empty-state', 'Data unavailable'));
    }
    document.getElementById('disk-updated').textContent = 'Not updating';
  } finally {busy = false;}
}
if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', refresh);
  refresh(); setInterval(refresh, 15000);
}
if (typeof module !== 'undefined') module.exports = {metric, hostMemory, limitCaption, sum, cpuShare, storageOrder, ceiling, ageText};
