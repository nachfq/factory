#!/usr/bin/env python3
"""Navigate an existing local Neovim without editing text or consuming selections."""

import argparse
import json
from pathlib import Path
import stat
import subprocess
import sys


LUA = r'''(function()
  local data = _A
  local ok, result = pcall(function()
    if vim.fn.mode() ~= "n" or vim.api.nvim_win_get_config(0).relative ~= "" or vim.bo.buftype == "prompt" then
      error("Editor is busy; finish the active input or floating dialog before displaying a file")
    end
    local buf
    for _, candidate in ipairs(vim.api.nvim_list_bufs()) do
      if vim.uv.fs_realpath(vim.api.nvim_buf_get_name(candidate)) == data.path then
        buf = candidate; break
      end
    end
    buf = buf or vim.fn.bufadd(data.path)
    vim.fn.bufload(buf)
    local count = vim.api.nvim_buf_line_count(buf)
    if data.line < 1 or data.last < data.line or data.last > count then
      error("Requested line range is outside the editor buffer")
    end
    local current = vim.api.nvim_get_current_win()
    local candidates = {}
    for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
      local wb = vim.api.nvim_win_get_buf(win)
      if vim.api.nvim_win_get_config(win).relative == "" and vim.bo[wb].buftype == "" then
        candidates[#candidates + 1] = win
      end
    end
    local win
    for _, candidate in ipairs(candidates) do
      if vim.api.nvim_win_get_buf(candidate) == buf then win = candidate; break end
      if candidate == current then win = candidate end
    end
    win = win or candidates[1]
    if not win then error("No normal source window is available") end
    vim.api.nvim_win_set_buf(win, buf)
    vim.api.nvim_set_current_win(win)
    vim.api.nvim_win_set_cursor(win, { data.line, 0 })
    vim.api.nvim_win_call(win, function() vim.cmd("normal! zvzz") end)

    local ns = vim.api.nvim_create_namespace("herdr_codex_reveal")
    for _, loaded in ipairs(vim.api.nvim_list_bufs()) do
      if vim.api.nvim_buf_is_loaded(loaded) then vim.api.nvim_buf_clear_namespace(loaded, ns, 0, -1) end
    end
    vim.g.herdr_codex_reveal_generation = (vim.g.herdr_codex_reveal_generation or 0) + 1
    local generation = vim.g.herdr_codex_reveal_generation
    if data.highlight_ms > 0 then
      vim.api.nvim_set_hl(0, "HerdrCodexReveal", { default = true, link = "Visual" })
      for row = data.line - 1, data.last - 1 do
        vim.api.nvim_buf_set_extmark(buf, ns, row, 0, { line_hl_group = "HerdrCodexReveal", priority = 150 })
      end
      if not vim.b[buf].herdr_codex_reveal_watch then
        local function changed()
          if vim.api.nvim_buf_is_valid(buf) then vim.api.nvim_buf_clear_namespace(buf, ns, 0, -1) end
        end
        vim.b[buf].herdr_codex_reveal_watch = vim.api.nvim_buf_attach(buf, false, {
          on_lines = changed, on_reload = changed,
          on_detach = function()
            if vim.api.nvim_buf_is_valid(buf) then vim.b[buf].herdr_codex_reveal_watch = nil end
          end,
        })
      end
      vim.defer_fn(function()
        if generation == vim.g.herdr_codex_reveal_generation and vim.api.nvim_buf_is_valid(buf) then
          vim.api.nvim_buf_clear_namespace(buf, ns, 0, -1)
        end
      end, data.highlight_ms)
    end
    return { status = "ok", file = vim.api.nvim_buf_get_name(buf), line = data.line,
      end_line = data.last, modified = vim.bo[buf].modified, highlight_ms = data.highlight_ms }
  end)
  return vim.json.encode(ok and result or { status = "error", message = tostring(result) })
end)()'''


def expression(payload):
    # Vim's single-quoted string contains literal JSON; no request data is code.
    data = json.dumps(payload, ensure_ascii=True).replace("'", "''")
    return 'luaeval(' + json.dumps(LUA) + ", json_decode('" + data + "'))"


def show(server, filename, line=1, end_line=None, highlight_ms=0):
    socket = Path(server).expanduser().absolute()
    if not stat.S_ISSOCK(socket.stat().st_mode):
        raise ValueError('Choose an existing local Neovim Unix socket')
    path = Path(filename).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError('Choose an existing regular file')
    last = line if end_line is None else end_line
    if not 1 <= line <= last or not 0 <= highlight_ms <= 60000:
        raise ValueError('Use a positive ordered line range and a highlight duration of 0–60000 ms')
    result = subprocess.run(
        ['nvim', '--server', str(socket), '--remote-expr', expression(
            dict(path=str(path), line=line, last=last, highlight_ms=highlight_ms))],
        capture_output=True, text=True, check=True, timeout=4,
    )
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', required=True)
    parser.add_argument('--file', required=True)
    parser.add_argument('--line', type=int, default=1)
    parser.add_argument('--end-line', type=int)
    parser.add_argument('--highlight-ms', type=int, default=0)
    args = parser.parse_args()
    result = show(args.server, args.file, args.line, args.end_line, args.highlight_ms)
    print(json.dumps(result))
    return 0 if result.get('status') == 'ok' else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        sys.exit(f'Could not display file: {error}')
