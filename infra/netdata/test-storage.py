"""Exercise stale values, removal and filesystem accounting without scanning guests."""
import importlib.util
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("collector", Path(__file__).with_name("collect-storage.py"))
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class StorageTests(unittest.TestCase):
    def test_publish_failure_preserves_snapshot_and_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "dashboard" / "incus-storage.json"
            data = dict(filesystems=[], instances=[], benchmark={"instances": []})
            with patch("sys.argv", ["collector", "--statsd", "--output", str(output)]), \
                 patch.object(collector, "snapshot", return_value=data), \
                 patch.object(collector, "publish_statsd", side_effect=OSError("collector unreachable")), \
                 patch.object(collector.os, "nice"), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    collector.main()
            self.assertEqual(error.exception.code, 1)
            self.assertEqual(json.loads(output.read_text())["statsd_error"], "collector unreachable")

    def test_publish_fresh_samples_only(self):
        def item(name, **kwargs):
            return dict(name=name, status="Running", used_bytes=1073741824,
                        measured_at=101, **kwargs)
        items = [item("fresh"), item("failed", error="du failed"), item("old"), item("stopped")]
        items[2]["measured_at"] = 99
        items[3]["status"] = "Stopped"
        result = dict(updated_at=100, filesystems=[dict(path="/", used_bytes=1073741824,
                      available_bytes=2147483648, reserved_bytes=536870912)], instances=items)
        payload = collector.statsd_payload(result).decode()
        self.assertIn("factory.incus.fresh.used:1.000000000|g", payload)
        self.assertIn("factory.host.root.available:2.000000000|g", payload)
        self.assertIn("factory.host.root.reserved:0.500000000|g", payload)
        self.assertIn("factory.collector.failures:1|g", payload)
        for name in ("failed", "old", "stopped"):
            self.assertNotIn(f"factory.incus.{name}.used", payload)
        items[0]["name"] = "bad\ninjected:99|g"
        with self.assertRaises(ValueError):
            collector.statsd_payload(result)

    def test_stopped_failed_deleted_and_unmanaged(self):
        def instance(name, status="Running", managed=True):
            return {"name": name, "status": status,
                    "config": {"user.agent-env": "true" if managed else "false"}}
        listing = [instance("new"), instance("stopped", "Stopped"),
                   instance("failed"), instance("changing"), instance("unmanaged", managed=False)]
        previous = {"instances": [{"name": name, "used_bytes": 42, "measured_at": 100}
                                   for name in ("stopped", "failed", "changing", "deleted")]}
        called = []
        def measure(name):
            called.append(name)
            if name == "failed":
                raise subprocess.TimeoutExpired("incus", 140)
            base = dict(cpu_seconds=0.1, disk_read_bytes=0)
            return dict(base, error="du failed") if name == "changing" else dict(base, used_bytes=999)
        with patch.object(collector.subprocess, "check_output", return_value=json.dumps(listing)):
            result = collector.snapshot(previous, ["/"], measure)
        by_name = {i["name"]: i for i in result["instances"]}
        self.assertEqual(called, ["new", "failed", "changing"])
        self.assertNotIn("deleted", by_name)
        self.assertNotIn("unmanaged", by_name)
        self.assertEqual(by_name["new"]["used_bytes"], 999)
        for name in ("stopped", "failed", "changing"):
            self.assertEqual(by_name[name]["used_bytes"], 42)
            self.assertEqual(by_name[name]["measured_at"], 100)
        self.assertIn("error", by_name["failed"])
        self.assertIn("error", by_name["changing"])
        fs = result["filesystems"][0]
        self.assertEqual(fs["used_bytes"]+fs["available_bytes"]+fs["reserved_bytes"], fs["total_bytes"])

    def test_instance_name_is_one_argument(self):
        with patch.object(collector.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, '{"used_bytes":123}', '')
            self.assertEqual(collector.collect_instance("space;echo nope")["used_bytes"], 123)
            argv = run.call_args.args[0]
            self.assertEqual(argv[:4], ["incus", "exec", "space;echo nope", "--"])
            self.assertNotIn("shell", run.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
