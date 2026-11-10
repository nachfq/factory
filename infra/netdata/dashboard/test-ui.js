/* DOM behavior only: no browser/layout rendering or external test dependency. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor(tag) {this.tag=tag; this.children=[]; this.style={}; this.attrs={}; this.events={}; this.clientWidth=400; this.textContent='';}
  append(...children) {this.children.push(...children);}
  replaceChildren(...children) {this.children=children;}
  setAttribute(key,value) {this.attrs[key]=String(value);}
  getAttribute(key) {return this.attrs[key] ?? null;}
  addEventListener(name,fn) {this.events[name]=fn;}
  getBoundingClientRect() {return {left:0,width:400};}
}
const walk = node => [node,...node.children.flatMap(walk)];
const text = node => walk(node).map(n=>n.textContent).join(' ');
const now = Math.floor(Date.now()/1000), GiB=1024**3;
const item = (name,size) => ({name,status:'Running',memory_limit:'2GiB',used_bytes:size*GiB,measured_at:now});
let snapshot = {hostname:'test-host',cpu_cores:4,updated_at:now,interval_seconds:600,
  filesystems:[{path:'/',used_bytes:100*GiB,available_bytes:400*GiB}],
  instances:[item('dev-small',2),item('dev-large',5)]};
let offline = false, noAvailable = false, noGuestMemory = false, nativeAPI = false;
const elements = Object.fromEntries(['host','instances','status','count','hostname','disk-updated'].map(id=>[id,new Element('div')]));
elements.host.setAttribute('aria-busy','true');
const document = {hidden:false,getElementById:id=>elements[id],
  createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag)};
const context = vm.createContext({console,URLSearchParams,AbortSignal,fetch:async url=>{
  if (offline) throw new Error('offline');
  if (url === 'incus-storage.json') return {ok:true,json:async()=>structuredClone(snapshot)};
  if (url === 'api/v1/info') return {ok:!nativeAPI,status:404,json:async()=>({})};
  if (url === '/api/v1/info') return {ok:true,json:async()=>({})};
  assert.equal(url.startsWith('/'),nativeAPI); // Scoped Serve API, or native Netdata fallback.
  const params = new URL(url,'http://test').searchParams, id=params.get('chart');
  assert.equal(Number(params.get('before'))-Number(params.get('after')),3600);
  if (id.includes('dev-new')) return {ok:false,status:404};
  if (noAvailable && id==='mem.available') return {ok:false,status:404};
  if (noGuestMemory && id.startsWith('factory_memory.')) return {ok:false,status:404};
  assert(!id.startsWith('cgroup_') || id.endsWith('.cpu')); // Never mix old RAM history with the new definition.
  const cpu = id.endsWith('.cpu'), hostRam=id==='system.ram', available=id==='mem.available';
  const dimensions=cpu?['user','system']:hostRam?['free','used','cached','buffers']:available?['avail']:['ram','swap'];
  const values=cpu?[20,10]:hostRam?[1024,2048,3072,0]:available?[4096]:[512,0];
  return {ok:true,json:async()=>({dimension_names:dimensions,latest_values:values,last_entry:now,
    after:now-3600,before:now,result:{data:[[now-60,...values],[now-20,...values]]}})};
}});
vm.runInContext(fs.readFileSync(`${__dirname}/app.js`,'utf8')+'\nglobalThis.runRefresh=refresh;',context);
context.document=document;
(async()=>{
  await context.runRefresh();
  assert.equal(elements.instances.children.length,2);
  assert(text(elements.instances.children[0]).includes('large'));
  assert(text(elements.instances.children[0]).includes('7.5')); // 30% of one core / four host cores.
  assert(text(elements.instances.children[0]).includes('of 2 GiB'));
  assert(text(elements.host).includes('4 GiB available'));
  assert.equal(elements.status.textContent,'Live');
  noGuestMemory=true;
  await context.runRefresh();
  assert(text(elements.instances.children[0]).includes('No data'));
  assert.equal(elements.status.textContent,'Pending data');
  noGuestMemory=false;
  await context.runRefresh();
  const plots=walk(elements.host).filter(n=>n.className==='plot');
  assert.equal(plots.length,2);
  assert(!walk(elements.host).some(n=>n.attrs.d?.includes('NaN')));
  plots[0].events.pointermove({clientX:100});
  assert(walk(plots[0]).some(n=>n.tag==='output' && !n.hidden && n.textContent.includes('30%')));
  snapshot.instances.push(item('dev-new',8));
  await context.runRefresh();
  assert.equal(elements.instances.children.length,3);
  assert(text(elements.instances.children[0]).includes('new'));
  assert(text(elements.instances.children[0]).includes('No data'));
  assert.equal(elements.status.textContent,'Pending data');
  snapshot.instances=snapshot.instances.filter(i=>i.name!=='dev-large');
  await context.runRefresh();
  assert.equal(elements.instances.children.length,2);
  assert(!text(elements.instances).includes('large'));
  noAvailable=true;
  await context.runRefresh();
  assert(text(elements.host).includes('Available: —'));
  assert(text(elements.host).includes('No data'));
  noAvailable=false;
  nativeAPI=true;
  vm.runInContext('apiPrefixPromise = undefined;',context);
  await context.runRefresh();
  assert(text(elements.host).includes('4 GiB available'));
  offline=true;
  await context.runRefresh();
  assert.equal(elements.status.textContent,'Offline');
  assert.equal(elements.instances.children.length,2); // Preserve last view, rather than empty/zero data.
  console.log('Dashboard DOM behavior passed: live rows, sorting, tooltip, missing metrics and offline state');
})().catch(error=>{console.error(error);process.exitCode=1;});
