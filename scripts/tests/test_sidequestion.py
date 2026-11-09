import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock


SOURCE = Path(__file__).resolve().parents[2] / 'skills/sidequestion/scripts/sidequestion.py'
spec = importlib.util.spec_from_file_location('sidequestion', SOURCE)
sq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sq)
PARENT = '00000000-0000-4000-8000-000000000001'
CHILD = '00000000-0000-4000-8000-000000000002'
OTHER = '00000000-0000-4000-8000-000000000003'


class SidequestionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sidequestion test ')
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {'XDG_RUNTIME_DIR': self.temp.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.directory = sq.runtime_root() / 'sq-test'
        self.directory.mkdir(mode=0o700)
        self.state = dict(token='sq-test', parent=PARENT, thread=CHILD,
                          workspace='w-test', tab='w-test:t1', pane='w-test:p1',
                          cwd=self.temp.name, phase='ready', question='')
        sq.save(self.state)

    def test_fork_uses_returned_uuid_not_parent_or_latest_history(self):
        result = subprocess.CompletedProcess([], 0, json.dumps(
            {'type': 'thread.started', 'thread_id': CHILD}) + '\n', '')
        with patch.object(sq, 'run', return_value=result) as run:
            self.assertEqual(sq.fork_thread(PARENT, self.temp.name), CHILD)
        self.assertEqual(run.call_args.args[0][-1], PARENT)

    def test_fork_rejects_parent_uuid(self):
        result = subprocess.CompletedProcess([], 0, json.dumps(
            {'type': 'thread.started', 'thread_id': PARENT}) + '\n', '')
        with patch.object(sq, 'run', return_value=result):
            with self.assertRaises(ValueError):
                sq.fork_thread(PARENT, self.temp.name)

    def test_partial_failed_fork_preserves_exact_uuid_for_supervisor_cleanup(self):
        error = subprocess.CalledProcessError(1, ['codex'], output=json.dumps(
            {'type': 'thread.started', 'thread_id': CHILD}) + '\n')
        with patch.object(sq, 'run', side_effect=error) as run:
            with self.assertRaises(sq.ForkStartupError) as caught:
                sq.fork_thread(PARENT, self.temp.name)
        self.assertEqual(caught.exception.child, CHILD)
        run.assert_called_once()

    def test_cleanup_refuses_parent_before_closing_any_tab(self):
        self.state['thread'] = PARENT
        with patch.object(sq, 'run') as run, patch.object(sq, 'herdr') as herdr:
            with self.assertRaises(ValueError):
                sq.cleanup(self.state)
        run.assert_not_called()
        herdr.assert_not_called()

    def test_cleanup_deletes_only_child_and_never_queues_a_summary(self):
        with patch.object(sq, 'run') as run, patch.object(sq, 'herdr') as herdr:
            sq.cleanup(self.state)
            sq.cleanup(self.state)
        run.assert_called_once_with(['codex', 'delete', CHILD, '--force'])
        self.assertEqual(herdr.call_args.args, ('tab', 'close', 'w-test:t1'))

    def test_handoff_targets_recorded_parent_even_with_another_environment(self):
        args = argparse.Namespace(session='sq-test', summary='Keep this literal: $(false); "x"')
        with patch.dict(os.environ, {'CODEX_THREAD_ID': OTHER, 'SIDEQUESTION_PARENT': OTHER}), \
                patch.object(sq, 'run') as run:
            sq.handoff(args)
        argv = run.call_args.args[0]
        self.assertEqual(argv[:4], ['codex', 'queue', '--thread', PARENT])
        self.assertIn(args.summary, argv[-1])
        self.assertFalse((self.directory / 'closed').exists())

    def test_no_handoff_when_summary_is_empty(self):
        with patch.object(sq, 'run') as run:
            with self.assertRaises(ValueError):
                sq.handoff(argparse.Namespace(session='sq-test', summary='  '))
        run.assert_not_called()

    def test_workspace_selection_ignores_unrelated_focus(self):
        replies = [{'workspaces': [{'workspace_id': 'wanted'}, {'workspace_id': 'focused'}]},
                   {'agents': [{'workspace_id': 'wanted', 'cwd': self.temp.name},
                               {'workspace_id': 'focused', 'cwd': '/unrelated'}]}]
        with patch.object(sq, 'herdr', side_effect=replies), \
                patch.dict(os.environ, {'HERDR_WORKSPACE_ID': 'focused'}):
            self.assertEqual(sq.workspace_for(Path(self.temp.name)), 'wanted')

    def test_ambiguous_workspace_requires_explicit_choice(self):
        replies = [{'workspaces': [{'workspace_id': 'a'}, {'workspace_id': 'b'}]},
                   {'agents': [{'workspace_id': name, 'cwd': self.temp.name} for name in ['a', 'b']]}]
        with patch.object(sq, 'herdr', side_effect=replies):
            with self.assertRaises(ValueError):
                sq.workspace_for(Path(self.temp.name))

    def test_closed_tab_cleans_the_fork_without_messaging_parent(self):
        replies = [
            {'tab': {'tab_id': 'w-test:t1'}, 'root_pane': {'pane_id': 'w-test:p1'}},
            {'agent': {'agent': 'codex'}}, {}, {'panes': []}, {},
        ]
        with patch.object(sq, 'fork_thread', return_value=CHILD), \
                patch.object(sq, 'herdr', side_effect=replies), patch.object(sq, 'run') as run:
            sq.supervise('sq-test')
        self.assertFalse(self.directory.exists())
        commands = [c.args[0] for c in run.call_args_list]
        self.assertIn(['codex', 'delete', CHILD, '--force'], commands)
        self.assertFalse(any(c[:2] == ['codex', 'queue'] for c in commands))

    def test_failed_cleanup_keeps_the_exact_child_for_retry(self):
        replies = [
            {'tab': {'tab_id': 'w-test:t1'}, 'root_pane': {'pane_id': 'w-test:p1'}},
            {'agent': {'agent': 'codex'}}, {}, {'panes': []}, {},
        ]
        def fail_delete(argv, **kwargs):
            if argv[:2] == ['codex', 'delete']:
                raise subprocess.CalledProcessError(1, argv)
            return Mock()
        with patch.object(sq, 'fork_thread', return_value=CHILD), \
                patch.object(sq, 'herdr', side_effect=replies), \
                patch.object(sq, 'run', side_effect=fail_delete):
            sq.supervise('sq-test')
        state = sq.load('sq-test')
        self.assertEqual(state['phase'], 'error')
        self.assertEqual(state['thread'], CHILD)
        self.assertEqual(state['parent'], PARENT)

    def test_late_fork_failure_also_retains_child_when_cleanup_fails(self):
        self.state.pop('thread')
        self.state.pop('tab')
        sq.save(self.state)
        with patch.object(sq, 'fork_thread', side_effect=sq.ForkStartupError(CHILD, 'late failure')), \
                patch.object(sq, 'run', side_effect=subprocess.CalledProcessError(1, ['codex'])):
            sq.supervise('sq-test')
        state = sq.load('sq-test')
        self.assertEqual(state['phase'], 'error')
        self.assertEqual(state['thread'], CHILD)
        self.assertEqual(state['parent'], PARENT)

    def test_session_token_cannot_traverse_runtime_directory(self):
        for value in ['../sq-other', '/tmp/sq-other', 'sq-a/../sq-other']:
            with self.assertRaises(ValueError):
                sq.state_dir(value)


if __name__ == '__main__':
    unittest.main()
