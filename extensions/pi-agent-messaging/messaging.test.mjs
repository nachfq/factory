import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtemp, rm, stat, chmod, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createConnection, createServer } from 'node:net';
import { randomUUID } from 'node:crypto';
import extension from './extension.mjs';
import dialogFixture from './fixtures/dialog.mjs';
import { identity, linkPeer, listen, send, MAX_BYTES, MAX_PENDING } from './messaging.mjs';

const tick = () => new Promise((resolve) => setImmediate(resolve));

test('dialog fixture records cancellation without authorizing an action', async () => {
  let command;
  const entries = [];
  dialogFixture({
    registerCommand: (_name, definition) => { command = definition; },
    appendEntry: (type, data) => entries.push({ type, ...data }),
  });
  await command.handler('', { ui: {
    confirm: async (_title, text, options) => {
      assert.match(text, /Neither answer authorizes/);
      assert.equal(options.timeout, 30000);
      assert.equal(entries.length, 1);
      return false;
    },
    notify() {},
  } });
  assert.deepEqual(entries.map(({ phase, confirmed }) => ({ phase, confirmed })), [
    { phase: 'opened', confirmed: undefined }, { phase: 'closed', confirmed: false },
  ]);
});

async function directory(t) {
  const path = await mkdtemp(join(tmpdir(), 'pi-msg-'));
  t.after(() => rm(path, { recursive: true, force: true }));
  return path;
}

async function pair(t) {
  const root = await directory(t);
  const a = await identity(root, 'session-a');
  const b = await identity(root, 'session-b');
  await linkPeer(a, b.path);
  await linkPeer(b, a.path);
  return { root, a, b };
}

function raw(socketPath, frame) {
  return new Promise((resolve, reject) => {
    const socket = createConnection(socketPath);
    let response = '';
    socket.setTimeout(1000, () => socket.destroy(new Error('Test timed out.')));
    socket.on('connect', () => socket.write(frame));
    socket.on('data', (data) => { response += data; });
    socket.on('end', () => resolve(JSON.parse(response)));
    socket.on('error', reject);
  });
}

function fakePi(root, session) {
  const handlers = new Map();
  const commands = new Map();
  const tools = new Map();
  const messages = [];
  const notifications = [];
  let idle = true;
  const ctx = {
    isIdle: () => idle,
    sessionManager: { getSessionId: () => session },
    ui: { notify: (...args) => notifications.push(args) },
  };
  const pi = {
    on: (name, handler) => handlers.set(name, handler),
    registerFlag() {},
    getFlag: () => root,
    registerCommand: (name, command) => commands.set(name, command),
    registerTool: (tool) => tools.set(tool.name, tool),
    sendMessage: (message, options) => {
      messages.push({ message, options });
      idle = false;
    },
  };
  extension(pi);
  return {
    messages, notifications, tools,
    event: async (name, event = {}) => handlers.get(name)?.(event, ctx),
    command: async (name, args = '') => commands.get(name).handler(args, ctx),
    idle: (value) => { idle = value; },
    consume: async () => {
      const last = messages.at(-1).message;
      await handlers.get('message_start')({ message: { role: 'custom', ...last } }, ctx);
    },
  };
}

async function sessions(t) {
  const root = await directory(t);
  const a = fakePi(root, 'session-a');
  const b = fakePi(root, 'session-b');
  await a.event('session_start');
  await b.event('session_start');
  t.after(async () => { await a.event('session_shutdown'); await b.event('session_shutdown'); });
  const ia = await identity(root, 'session-a');
  const ib = await identity(root, 'session-b');
  await a.command('agent-link', ib.path);
  await b.command('agent-link', ia.path);
  const message = (content) => a.tools.get('agent_message').execute('call', { recipient: 'session-b', content });
  return { root, a, b, ia, ib, message };
}

test('identity and links persist, new/fork IDs differ, files are private', async (t) => {
  const { root, a, b } = await pair(t);
  const resumed = await identity(root, a.session);
  assert.equal(resumed.socket, a.socket);
  assert.equal(resumed.token, a.token);
  assert.deepEqual(resumed.peers, a.peers);
  assert.notEqual(a.socket, b.socket);
  const fork = await identity(root, 'forked-session');
  assert.notEqual(fork.token, a.token);
  assert.deepEqual(fork.peers, []);
  assert.equal((await stat(root)).mode & 0o777, 0o700);
  assert.equal((await stat(a.path)).mode & 0o777, 0o600);
  await chmod(root, 0o755);
  await assert.rejects(identity(root, 'other'), /private/);
});

test('explicit linking checks private contact files', async (t) => {
  const { a, b } = await pair(t);
  await chmod(b.path, 0o644);
  await assert.rejects(linkPeer(a, b.path), /private/);
});

test('real sockets accept authenticated messages and strip credentials', async (t) => {
  const { a, b } = await pair(t);
  const inbox = [];
  const stop = await listen(b, (message) => inbox.push(message));
  t.after(stop);
  const reply = await send(a, b.session, 'Hello\nfrom A');
  assert.equal(reply.accepted, true);
  assert.equal(reply.id, inbox[0].id);
  assert.equal(inbox[0].content, 'Hello\nfrom A');
  assert.equal('credential' in inbox[0], false);
});

test('malformed, wrong-session, unlinked, oversized, and multi-frame sends are rejected', async (t) => {
  const { a, b } = await pair(t);
  let count = 0;
  const stop = await listen(b, () => count++);
  t.after(stop);
  const envelope = { version: 1, id: randomUUID(), sender: a.session, recipient: b.session, content: 'Hello', credential: b.token };
  for (const frame of [
    '{not json}\n',
    JSON.stringify({ ...envelope, recipient: 'another-session' }) + '\n',
    JSON.stringify({ ...envelope, sender: 'unlinked' }) + '\n',
    JSON.stringify({ ...envelope, credential: 'wrong' }) + '\n',
    JSON.stringify({ ...envelope, content: '' }) + '\n',
    JSON.stringify(envelope) + '\n{}\n',
    'x'.repeat(MAX_BYTES + 1),
  ]) assert.equal((await raw(b.socket, frame)).accepted, false);
  assert.equal(count, 0);
  await assert.rejects(send(a, b.session, 'é'.repeat(MAX_BYTES)), /16 KiB/);
  await assert.rejects(send(a, 'not-linked', 'Hi'), /not linked/);
});

test('fragmented UTF-8 frames are buffered until the newline', async (t) => {
  const { a, b } = await pair(t);
  const inbox = [];
  const stop = await listen(b, (message) => inbox.push(message));
  t.after(stop);
  const frame = Buffer.from(JSON.stringify({ version: 1, id: randomUUID(), sender: a.session, recipient: b.session, content: '¿Listo?', credential: b.token }) + '\n');
  const socket = createConnection(b.socket);
  t.after(() => socket.destroy());
  await new Promise((resolve, reject) => { socket.once('connect', resolve); socket.once('error', reject); });
  const response = new Promise((resolve) => socket.once('data', (data) => resolve(JSON.parse(data))));
  const split = frame.indexOf(Buffer.from('¿')) + 1;
  socket.write(frame.subarray(0, split));
  await tick();
  assert.equal(inbox.length, 0);
  socket.write(frame.subarray(split));
  assert.equal((await response).accepted, true);
  assert.equal(inbox[0].content, '¿Listo?');
});

test('an active receiver collision is refused without unlinking it; shutdown removes socket', async (t) => {
  const { a, b } = await pair(t);
  const stop = await listen(b, () => {});
  try {
    await assert.rejects(listen(b, () => {}), { code: 'EADDRINUSE' });
    assert.equal((await send(a, b.session, 'Still alive')).accepted, true);
  } finally { await stop(); }
  await assert.rejects(stat(b.socket), { code: 'ENOENT' });
  await assert.rejects(send(a, b.session, 'Closed'), /unavailable/);
});

test('missing replies and cancellation after sending are unconfirmed, without retry', async (t) => {
  const { a, b } = await pair(t);
  let connections = 0;
  const sockets = new Set();
  const server = createServer((socket) => {
    connections++;
    sockets.add(socket);
    socket.on('data', () => {});
    socket.on('close', () => sockets.delete(socket));
  });
  await new Promise((resolve) => server.listen(b.socket, resolve));
  t.after(async () => {
    for (const socket of sockets) socket.destroy();
    await new Promise((resolve) => server.close(resolve));
  });
  await assert.rejects(send(a, b.session, 'No reply', { timeout: 25 }), /unconfirmed/);
  assert.equal(connections, 1);
  const controller = new AbortController();
  const sending = send(a, b.session, 'Cancel', { signal: controller.signal });
  setTimeout(() => controller.abort(), 25);
  await assert.rejects(sending, /unconfirmed/);
  assert.equal(connections, 2);
});

test('idle recipient gets a visible custom followUp and a triggered turn, without secrets', async (t) => {
  const { a, b, ia, ib, message } = await sessions(t);
  const result = await message('Question: which check should I run?');
  await tick();
  assert.match(result.content[0].text, /accepted.*Reading and completion are not confirmed/);
  assert.equal(b.messages.length, 1);
  const delivered = b.messages[0];
  assert.deepEqual(delivered.options, { deliverAs: 'followUp', triggerTurn: true });
  assert.equal(delivered.message.customType, 'agent-event');
  assert.equal(delivered.message.display, true);
  assert.match(delivered.message.content, /not a human instruction or approval/);
  for (const secret of [ia.token, ib.token]) {
    assert.equal(JSON.stringify([a.notifications, b.notifications, result, delivered]).includes(secret), false);
  }
  await b.consume();
  const reply = await b.tools.get('agent_message').execute('reply', { recipient: ia.session, content: 'Ready for your answer.' });
  await tick();
  assert.equal(reply.details.accepted, true);
  assert.equal(a.messages.length, 1);
});

test('busy and dialog-open recipients retain bounded messages until idle and dialog closed', async (t) => {
  const { b, message } = await sessions(t);
  b.idle(false);
  for (let i = 0; i < MAX_PENDING; i++) await message(`Message ${i}`);
  await tick();
  assert.equal(b.messages.length, 0);
  await assert.rejects(message('Over capacity'), /rejected/);
  await b.event('ui_prompt_start');
  b.idle(true);
  await b.event('agent_settled');
  await tick();
  assert.equal(b.messages.length, 0);
  await b.event('ui_prompt_end');
  await tick();
  assert.equal(b.messages.length, 1);
  // Count the message handed to Pi until its message_start is observed.
  await assert.rejects(message('Still full'), /rejected/);
  await b.consume();
  await message('Space freed');
  assert.equal(b.messages.length, 1); // Work is active; no interruption.
  b.idle(true);
  await b.event('agent_settled');
  await tick();
  assert.equal(b.messages.length, 2);
});

test('shutdown drops pending contents; reload/resume preserve identity and links, not inbox', async (t) => {
  const { root, b, ib, message } = await sessions(t);
  b.idle(false);
  await message('Old pending message');
  await b.event('session_shutdown');
  const replacement = fakePi(root, ib.session);
  await replacement.event('session_start', { reason: 'reload' });
  t.after(() => replacement.event('session_shutdown'));
  await tick();
  assert.equal(replacement.messages.length, 0);
  const saved = JSON.parse(await readFile(ib.path, 'utf8'));
  assert.equal(saved.token, ib.token);
  assert.equal(JSON.stringify(saved).includes('Old pending message'), false);
  await message('Fresh message after reload');
  await tick();
  assert.equal(replacement.messages.length, 1);
  await replacement.event('session_shutdown');
  const another = fakePi(root, 'new-conversation');
  await another.event('session_start', { reason: 'new' });
  t.after(() => another.event('session_shutdown'));
  await assert.rejects(message('Old conversation closed'), /unavailable/);
  await tick();
  assert.equal(another.messages.length, 0);
});
