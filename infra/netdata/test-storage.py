"""Exercise stale values, removal and filesystem accounting without scanning guests."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("collector", Path(__file__).with_name("collect-storage.py"))
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class StorageTests(unittest.TestCase):
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
