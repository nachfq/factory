import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("dashboard", Path(__file__).with_name("make-dashboard.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DashboardTests(unittest.TestCase):
    def test_explicit_instance_and_dimension_selection(self):
        template = json.loads(Path(__file__).with_name("native-card-template.json").read_text())
        snapshot = {"hostname": "host", "instances": [{"name": "dev-example"}]}
        charts = {"system.cpu": {"context": "system.cpu"}, "system.ram": {"context": "system.ram"},
                  "statsd_factory.host_disk_space": {"context": "statsd_factory.host_disk_space"},
                  "cgroup_dev-example.cpu": {"context": "cgroup.cpu"},
                  "cgroup_dev-example.mem_usage": {"context": "cgroup.mem_usage"},
                  "statsd_factory.incus.dev-example.used_gauge": {"context": "statsd_factory.incus.dev-example.used_gauge"},
                  "cgroup_docker.cpu": {"context": "cgroup.cpu"}}
        d = module.build_dashboard(template, snapshot, charts)
        self.assertEqual(len(d["cards"]), 6)
        self.assertEqual({x["id"] for x in d["layout"]["A"]}, set(d["cards"]))
        cpu = next(c for c in d["cards"].values() if c["contextScope"] == ["cgroup.cpu"])
        self.assertEqual(cpu["selectedInstances"], ["cgroup_dev-example.cpu"])
        self.assertEqual((cpu["groupBy"], cpu["aggregationMethod"]), (["selected"], "sum"))
        ram = next(c for c in d["cards"].values() if c["contextScope"] == ["cgroup.mem_usage"])
        self.assertEqual(ram["selectedDimensions"], ["ram"])
        host_ram = next(c for c in d["cards"].values() if c["contextScope"] == ["system.ram"])
        self.assertEqual(host_ram["selectedDimensions"], ["used"])
        del charts["statsd_factory.incus.dev-example.used_gauge"]
        with self.assertRaisesRegex(ValueError, "run storage collection first"):
            module.build_dashboard(template, snapshot, charts)


if __name__ == "__main__":
    unittest.main()
