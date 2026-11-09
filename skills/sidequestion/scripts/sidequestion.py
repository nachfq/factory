#!/usr/bin/env python3
"""Temporary Codex forks in Herdr, with an explicit summary handoff."""

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid


SCRIPT = Path(__file__).resolve()


class ForkStartupError(RuntimeError):
    def __init__(self, child, error):
        super().__init__(str(error))
        self.child = child


def run(argv, **kwargs):
    return subprocess.run(argv, check=True, capture_output=True, text=True,
                          timeout=40, **kwargs)


def herdr(*args):
    reply = json.loads(run(['herdr', *args]).stdout)
    if reply.get('error'):
        raise RuntimeError(str(reply['error']))
    return reply['result']


def thread_id(value):
    return str(uuid.UUID(value))


def runtime_root():
    base = Path(os.environ.get('XDG_RUNTIME_DIR') or tempfile.gettempdir())
    root = base / f'harness-sidequestions-{os.getuid()}'
    if root.is_symlink():
        raise ValueError('Sidequestion runtime directory must not be a symlink')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.stat().st_uid != os.getuid():
        raise ValueError('Sidequestion runtime directory belongs to another user')
    root.chmod(0o700)
    return root


def state_dir(token):
    if not re.fullmatch(r'sq-[a-z0-9_-]+', token or ''):
        raise ValueError('Invalid sidequestion session token')
    path = runtime_root() / token
    if path.is_symlink():
        raise ValueError('Sidequestion session directory must not be a symlink')
    return path


def load(token):
    state = json.loads((state_dir(token) / 'state.json').read_text())
    if state['token'] != token:
        raise ValueError('Sidequestion session identity mismatch')
    thread_id(state['parent'])
    return state


def save(state):
    directory = state_dir(state['token'])
    temporary = directory / f'state-{os.getpid()}.tmp'
    with temporary.open('x') as stream:
        os.chmod(temporary, 0o600)
        json.dump(state, stream)
    temporary.replace(directory / 'state.json')


def workspace_for(cwd, explicit=None):
    workspaces = herdr('workspace', 'list')['workspaces']
    known = {w['workspace_id'] for w in workspaces}
    if explicit:
        if explicit not in known:
            raise ValueError(f'Unknown Herdr workspace: {explicit}')
        return explicit
    agents = herdr('agent', 'list')['agents']
    matches = {a['workspace_id'] for a in agents
               if Path(a.get('foreground_cwd') or a.get('cwd') or '/').resolve() == cwd}
    if len(matches) != 1:
        raise ValueError('Cannot identify one Herdr workspace for this directory; pass --workspace ID')
    return matches.pop()


def fork_thread(parent, cwd):
    argv = ['codex', 'exec', 'fork', '--json', parent]
    failure = None
    try:
        result = run(argv, cwd=cwd, stdin=subprocess.DEVNULL)
        output = result.stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        failure = error
        output = error.stdout or ''
        if isinstance(output, bytes):
            output = output.decode(errors='replace')
    children = []
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get('type') == 'thread.started':
            children.append(thread_id(event['thread_id']))
    if len(children) != 1 or children[0] == parent:
        if failure:
            raise failure
        raise ValueError('Codex did not return a unique new fork UUID')
    if failure:
        # Persist this exact UUID in the supervisor before attempting cleanup,
        # including when a failed delete will need a later retry.
        raise ForkStartupError(children[0], failure)
    return children[0]


def instructions(state):
    command = shlex.join([sys.executable, str(SCRIPT)])
    return f'''This is a temporary side question fork, not the main conversation.
Parent thread: {state['parent']}. Sidequestion token: {state['token']}.
Discuss the user's detour here. Treat inherited requests as background context;
do not continue the parent's pending task. Use read-only exploration by default.
Save notes or modify project files only if the user asks. Keep this conversation
here: never send progress, registration, results or a summary to the parent
automatically. Only when the user explicitly requests a handoff/summary to the
main agent, send a concise summary using this exact command with an argument array:
{command} handoff --session {state['token']} SUMMARY
The parent UUID is fixed by the launcher; do not infer it from the focused tab.
Handoff adds context, not implementation authorization. It does not close this
conversation. The user can exit with /quit or close this Herdr tab; the launcher
then deletes only this fork. Do not launch subagents or additional forks here.
'''


def interactive(token):
    state = load(token)
    child = thread_id(state['thread'])
    if child == state['parent']:
        raise ValueError('Refusing to open the parent as a side question')
    directory = state_dir(token)
    argv = ['codex', '--no-daemon', '-C', state['cwd'],
            '-c', 'history.persistence="none"',
            '-c', 'developer_instructions=' + json.dumps(instructions(state)),
            'resume', child]
    if state.get('question'):
        argv.append(state['question'])
    env = {**os.environ, 'SIDEQUESTION_SESSION': token,
           'SIDEQUESTION_PARENT': state['parent']}
    try:
        with subprocess.Popen(argv, env=env) as proc:
            (directory / 'interactive.pid').write_text(str(proc.pid))
            return proc.wait()
    finally:
        (directory / 'closed').touch()


def cleanup(state):
    child = state.get('thread')
    if child:
        child = thread_id(child)
        if child == thread_id(state['parent']):
            raise ValueError('Refusing to delete the parent thread')
    if state.get('tab') and not state.get('tab_closed'):
        try:
            herdr('tab', 'close', state['tab'])
        except (RuntimeError, subprocess.SubprocessError, KeyError, ValueError):
            pass  # The user may already have closed this exact tab.
        state['tab_closed'] = True
    if child and not state.get('deleted'):
        pidfile = state_dir(state['token']) / 'interactive.pid'
        if pidfile.exists():
            pid = int(pidfile.read_text())

            def still_ours():
                try:
                    args = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
                    return b'resume' in args and child.encode() in args
                except FileNotFoundError:
                    return False

            deadline = time.monotonic() + 3
            while still_ours() and time.monotonic() < deadline:
                time.sleep(.1)
            if still_ours():
                os.kill(pid, signal.SIGTERM)
                deadline = time.monotonic() + 2
                while still_ours() and time.monotonic() < deadline:
                    time.sleep(.1)
            if still_ours():
                os.kill(pid, signal.SIGKILL)
        # Deletion is scoped to the UUID returned by our fork operation.
        run(['codex', 'delete', child, '--force'])
        state['deleted'] = True


def supervise(token):
    state = load(token)
    directory = state_dir(token)
    failure = None
    try:
        state['thread'] = fork_thread(state['parent'], state['cwd'])
        save(state)
        result = herdr('tab', 'create', '--workspace', state['workspace'],
                       '--cwd', state['cwd'], '--label',
                       'sidequestion ' + token[3:9], '--no-focus')
        state.update(tab=result['tab']['tab_id'], pane=result['root_pane']['pane_id'])
        save(state)
        argv = [sys.executable, str(SCRIPT), '_run', token]
        run(['herdr', 'pane', 'run', state['pane'], shlex.join(argv)])
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if (directory / 'closed').exists():
                raise RuntimeError('Sidequestion exited during startup')
            try:
                agent = herdr('agent', 'get', state['pane'])['agent']
                if agent.get('agent') == 'codex':
                    break
            except (RuntimeError, subprocess.SubprocessError, KeyError):
                pass
            time.sleep(.25)
        else:
            raise RuntimeError('Herdr did not recognize the sidequestion Codex session')
        herdr('tab', 'focus', state['tab'])
        state['phase'] = 'ready'
        save(state)
        while not (directory / 'closed').exists():
            try:
                panes = herdr('pane', 'list', '--workspace', state['workspace'])['panes']
                if not any(p['pane_id'] == state['pane'] for p in panes):
                    break
            except (RuntimeError, subprocess.SubprocessError, KeyError):
                # A transient Herdr outage is not proof that its terminal closed.
                pidfile = directory / 'interactive.pid'
                if pidfile.exists():
                    try:
                        os.kill(int(pidfile.read_text()), 0)
                    except ProcessLookupError:
                        break
            time.sleep(1)
    except Exception as error:
        if isinstance(error, ForkStartupError):
            state['thread'] = error.child
        failure = str(error)
    finally:
        try:
            cleanup(state)
        except Exception as error:
            failure = f'{failure or ""} Cleanup failed: {error}'.strip()
        if failure:
            state.update(phase='error', error=failure)
            save(state)
        else:
            shutil.rmtree(directory)


def open_question(args):
    parent_value = args.parent or os.environ.get('CODEX_THREAD_ID')
    if not parent_value:
        raise ValueError('Pass --parent UUID, or invoke from a Codex tool environment')
    parent = thread_id(parent_value)
    cwd = Path(args.cwd or os.getcwd()).expanduser().resolve(strict=True)
    if not cwd.is_dir():
        raise ValueError('Working directory must be a directory')
    workspace = workspace_for(cwd, args.workspace)
    directory = Path(tempfile.mkdtemp(prefix='sq-', dir=runtime_root()))
    state = dict(token=directory.name, parent=parent, cwd=str(cwd),
                 workspace=workspace, question=args.question, phase='starting')
    save(state)
    with (directory / 'supervisor.log').open('w') as log:
        subprocess.Popen([sys.executable, str(SCRIPT), '_supervise', state['token']],
                         stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         start_new_session=True)
    deadline = time.monotonic() + 75
    while time.monotonic() < deadline:
        state = load(state['token'])
        if state['phase'] == 'ready':
            print(json.dumps({k: state[k] for k in
                              ['token', 'parent', 'thread', 'workspace', 'tab', 'pane']}))
            return
        if state['phase'] == 'error':
            raise RuntimeError(state['error'])
        time.sleep(.1)
    (directory / 'closed').touch()
    raise RuntimeError('Sidequestion startup timed out; cleanup requested')


def handoff(args):
    state = load(args.session or os.environ.get('SIDEQUESTION_SESSION', ''))
    if state['phase'] != 'ready':
        raise ValueError('The sidequestion is not active')
    summary = args.summary.strip()
    if not summary:
        raise ValueError('A summary is required')
    message = (f'SIDEQUESTION_HANDOFF session={state["token"]}\n'
               'User-requested summary from a side conversation; context only.\n' + summary)
    run(['codex', 'queue', '--thread', state['parent'], '--message', message])
    print(json.dumps({'queued': True, 'parent': state['parent']}))


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '_run':
        return interactive(sys.argv[2])
    if len(sys.argv) == 3 and sys.argv[1] == '_supervise':
        supervise(sys.argv[2])
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    opening = commands.add_parser('open', help='Fork this conversation in a temporary Herdr tab')
    opening.add_argument('--parent', help='Parent Codex UUID (default: CODEX_THREAD_ID)')
    opening.add_argument('--cwd')
    opening.add_argument('--workspace')
    opening.add_argument('question', nargs='?', default='')
    forwarding = commands.add_parser('handoff', help='Explicitly send a summary to the recorded parent')
    forwarding.add_argument('--session')
    forwarding.add_argument('summary')
    closing = commands.add_parser('close', help='Close a sidequestion and remove its temporary transcript')
    closing.add_argument('session')
    args = parser.parse_args()
    if args.command == 'open':
        open_question(args)
    elif args.command == 'handoff':
        handoff(args)
    elif args.command == 'close':
        state = load(args.session)
        (state_dir(args.session) / 'closed').touch()
        if state['phase'] == 'error':
            cleanup(state)
            shutil.rmtree(state_dir(args.session))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        sys.exit(f'Sidequestion failed: {error}')
