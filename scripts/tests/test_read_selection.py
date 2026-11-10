import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[2] / 'skills/herdr-nvim/scripts/read_selection.py'
spec = importlib.util.spec_from_file_location('read_selection', SOURCE)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class ReadSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'nvim "quoted" $(false).sock'
        self.server = socket.socket(socket.AF_UNIX)
        self.server.bind(str(self.path))
        self.addCleanup(self.server.close)

    def test_native_consumer_preserves_result_and_passes_socket_as_data(self):
        selected = dict(status='ok', selection=dict(text='Unsaved text', modified=True))
        result = subprocess.CompletedProcess([], 0, json.dumps(selected), '')
        with patch.object(reader.subprocess, 'run', return_value=result) as run:
            self.assertEqual(reader.read_selection(self.path), selected)
        self.assertEqual(run.call_args.args[0][:4], ['nvim', '--server', str(self.path), '--remote-expr'])
        self.assertIn('context.get_selection()', run.call_args.args[0][-1])
        self.assertNotIn('shell', run.call_args.kwargs)
        self.assertEqual(run.call_args.kwargs['timeout'], 4)

    def test_metadata_does_not_call_the_consumer(self):
        result = subprocess.CompletedProcess([], 0, '{"pid":123}', '')
        with patch.object(reader.subprocess, 'run', return_value=result) as run:
            self.assertEqual(reader.read_selection(self.path, metadata=True), {'pid': 123})
        self.assertIn('context.metadata()', run.call_args.args[0][-1])
        self.assertNotIn('get_selection', run.call_args.args[0][-1])

    def test_regular_files_and_foreign_sockets_are_rejected_before_rpc(self):
        regular = Path(self.temp.name) / 'not-a-socket'
        regular.touch()
        with patch.object(reader.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                reader.read_selection(regular)
            with patch.object(reader.os, 'getuid', return_value=os.getuid() + 1):
                with self.assertRaises(ValueError):
                    reader.read_selection(self.path)
        run.assert_not_called()

    def test_timeout_is_not_retried_because_a_read_may_have_consumed_the_selection(self):
        with patch.object(reader.subprocess, 'run', side_effect=subprocess.TimeoutExpired('nvim', 4)) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                reader.read_selection(self.path)
        run.assert_called_once()


if __name__ == '__main__':
    unittest.main()
