import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

loader = importlib.machinery.SourceFileLoader('factory_memory', str(Path(__file__).with_name('factory-memory.plugin')))
spec = importlib.util.spec_from_loader(loader.name, loader)
memory = importlib.util.module_from_spec(spec)
loader.exec_module(memory)
MiB = 1024**2


class MemoryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.snapshot = self.root/'snapshot.json'
        self.snapshot.write_text(json.dumps({'instances':[
            {'name':'dev-demo','status':'Running'}, {'name':'dev-stopped','status':'Stopped'},
            {'name':'dev-deleted','status':'Running'}]}))
        self.cgroup = self.root/'lxc.payload.dev-demo'
        self.cgroup.mkdir()
        (self.cgroup/'memory.current').write_text(str(1500*MiB))
        (self.cgroup/'memory.stat').write_text(f'inactive_file {400*MiB}\nslab_reclaimable {500*MiB}\n')

    def test_excludes_both_caches_and_skips_stopped_or_disappeared_guests(self):
        samples, errors = memory.collect(self.snapshot, self.root)
        self.assertEqual(samples, {'dev-demo':600*MiB})
        self.assertEqual(errors, [])

    def test_inconsistent_or_missing_counters_are_missing_data_not_false_zeroes(self):
        for stats in [f'inactive_file {1600*MiB}\nslab_reclaimable 0\n', 'inactive_file 0\n']:
            (self.cgroup/'memory.stat').write_text(stats)
            samples, errors = memory.collect(self.snapshot, self.root)
            self.assertEqual(samples, {})
            self.assertEqual(len(errors), 1)

    def test_services_without_dev_prefix_publish_memory_charts(self):
        (self.root/'lxc.payload.ollama').mkdir()
        (self.root/'lxc.payload.ollama/memory.current').write_text(str(900*MiB))
        (self.root/'lxc.payload.ollama/memory.stat').write_text(f'inactive_file {100*MiB}\nslab_reclaimable 0\n')
        self.snapshot.write_text(json.dumps({'instances': [{'name': 'ollama', 'status': 'Running'}]}))
        samples, errors = memory.collect(self.snapshot, self.root)
        self.assertEqual(samples, {'ollama': 800*MiB})
        self.assertEqual(errors, [])
        self.assertIn('CHART factory_memory.ollama', memory.render(samples, set(), 10))

    def test_unsafe_names_cannot_escape_the_cgroup_directory_or_inject_protocol(self):
        self.snapshot.write_text(json.dumps({'instances':[{'name':'dev-../../elsewhere','status':'Running'}]}))
        with self.assertRaises(ValueError):
            memory.collect(self.snapshot, self.root)

    def test_new_guests_define_charts_once_and_missing_guests_emit_no_zero(self):
        known=set()
        first=memory.render({'dev-demo':600*MiB},known,10)
        self.assertIn('CHART factory_memory.dev-demo',first)
        self.assertIn('DIMENSION ram',first)
        self.assertIn(f'SET ram = {600*MiB}',first)
        self.assertNotIn('CHART',memory.render({'dev-demo':700*MiB},known,10))
        self.assertIn('CHART factory_memory.dev-new',memory.render({'dev-new':MiB},known,10))
        self.assertEqual(memory.render({},known,10),'\n\n')


if __name__ == '__main__':
    unittest.main()
