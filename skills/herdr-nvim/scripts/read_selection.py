#!/usr/bin/env python3
"""Read one user-captured selection through an existing local Neovim socket."""

import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


def read_selection(server, metadata=False):
    socket = Path(server).expanduser().absolute()
    info = socket.stat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError('Choose an existing Neovim Unix socket owned by this user')
    method = 'metadata' if metadata else 'get_selection'
    lua = ('(function() local ok, context = pcall(require, "herdr-codex.context"); '
           'if not ok then return vim.json.encode({status="unavailable", '
           'message="The editor selection context plugin is not installed"}) end; '
           f'return vim.json.encode(context.{method}()) end)()')
    result = subprocess.run(['nvim', '--server', str(socket), '--remote-expr',
                             'luaeval(' + json.dumps(lua) + ')'],
                            capture_output=True, text=True, check=True, timeout=4)
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', required=True)
    parser.add_argument('--metadata', action='store_true', help='Identify the editor without consuming text')
    args = parser.parse_args()
    result = read_selection(args.server, args.metadata)
    print(json.dumps(result))
    ok = 'pid' in result if args.metadata else result.get('status') == 'ok'
    return 0 if ok else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        sys.exit(f'Could not read selection: {error}')
