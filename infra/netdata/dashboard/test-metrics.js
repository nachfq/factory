const assert = require('node:assert/strict');
const {metric, hostMemory, limitCaption, sum, cpuShare, storageOrder, ceiling, ageText} = require('./app.js');
const data = {dimension_names:['free','used','cached','buffers'], latest_values:[1024,2048,4096,1024],
  last_entry:50, after:0, before:50, result:{data:[[50,512,1024,2048,512],[20,null,null,null,null]]}};
const ram = metric(data, 'host-ram');
assert.equal(ram.current, 2); // Current value, not the historical bucket average.
assert.equal(ram.total, 8);
assert.deepEqual(ram.points, [[20,null],[50,1]]);
const available = metric({...data, dimension_names:['avail'], latest_values:[5120], last_entry:49,
  result:{data:[[50,6144],[20,null]]}}, 'available');
const host = hostMemory(ram,available);
assert.equal(host.current,3); // Total 8 GiB minus 5 GiB available, rather than the old 2 GiB "used" field.
assert.equal(host.available,5);
assert.equal(host.total,8);
assert.equal(host.last,49);
assert.deepEqual(host.points,[[20,null],[50,2]]);
assert.equal(hostMemory(ram,null),null);
assert.equal(hostMemory({...ram,total:null},available),null);
assert.equal(hostMemory(ram,{...available,current:null}).current,null);
assert.equal(hostMemory(ram,{...available,current:9}).available,null);
assert.equal(metric({...data,latest_values:[1024,null,4096,1024]},'host-ram').total,null);
assert.equal(limitCaption('2GiB'),'of 2 GiB');
assert.equal(limitCaption('2147483648'),'of 2 GiB');
assert.equal(limitCaption('512MiB'),'of 512 MiB');
assert.equal(limitCaption('50%'),'Limit: 50% of host');
assert.equal(limitCaption(null),'No limit');
assert.equal(limitCaption('unknown'),'Limit unavailable');
const guest = metric({...data, dimension_names:['ram','swap'], latest_values:[512,2048],
  result:{data:[[50,256,1024]]}}, 'ram');
assert.equal(guest.current, 0.5); // Swap isn't resident RAM.
const cpu = metric({...data, dimension_names:['user','system'], latest_values:[125,25],
  result:{data:[[50,100,10]]}}, 'cpu');
assert.equal(cpu.current, 150); // Container CPU can exceed 100% of one core.
assert.equal(sum([null,null]), null);
assert.equal(sum([1,null,2]), 3);
const share = cpuShare(cpu, 4);
assert.equal(share.current, 37.5); // Same denominator as the host's CPU percentage.
assert.equal(share.points[0][1], 27.5);
assert.equal(cpu.current, 150); // Raw data remains unchanged.
assert.equal(cpuShare(cpu, 0), null);
assert.equal(cpuShare({...cpu, current:null, points:[[1,null]]}, 4).points[0][1], null);
const items = [{name:'small',used_bytes:10}, {name:'unknown'}, {name:'big',used_bytes:500}];
assert.deepEqual(storageOrder(items).map(i=>i.name), ['big','small','unknown']);
assert.equal(items[0].name, 'small'); // Rendering doesn't mutate the source snapshot.
assert.deepEqual(storageOrder([...items,{name:'new',used_bytes:1000}]).map(i=>i.name), ['new','big','small','unknown']);
assert.deepEqual(storageOrder(items.filter(i=>i.name!=='big')).map(i=>i.name), ['small','unknown']);
assert.equal(ceiling([cpuShare(cpu,4),null],10),50);
assert.equal(ceiling([null],10),10);
assert.equal(ceiling([ram,guest],.5),2);
assert.equal(ageText(1000,1000), 'now');
assert.equal(ageText(1000,1180), '3m ago');
console.log('Metric transformations passed');
