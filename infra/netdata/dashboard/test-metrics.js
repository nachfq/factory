const assert = require('node:assert/strict');
const {metric, sum} = require('./app.js');
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
console.log('Metric transformations passed');
