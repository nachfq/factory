const assert = require('node:assert/strict');
const {metric, sum, cpuShare, storageOrder, ceiling, ageText} = require('./app.js');
const data = {dimension_names:['free','used','cached','buffers'], latest_values:[1024,2048,4096,1024],
  last_entry:50, after:0, before:50, result:{data:[[50,512,1024,2048,512],[20,null,null,null,null]]}};
const ram = metric(data, 'host-ram');
assert.equal(ram.current, 2); // Current value, not the historical bucket average.
assert.equal(ram.total, 8);
assert.deepEqual(ram.points, [[20,null],[50,1]]);
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
assert.equal(ageText(1000,1000), 'ahora');
assert.equal(ageText(1000,1180), 'hace 3 min');
console.log('Metric transformations passed');
