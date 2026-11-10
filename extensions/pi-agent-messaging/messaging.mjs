import { randomBytes, randomUUID, createHash, timingSafeEqual } from 'node:crypto';
import { mkdir, lstat, readFile, writeFile } from 'node:fs/promises';
import { createServer, createConnection } from 'node:net';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';

export const MAX_BYTES = 16 * 1024;
export const MAX_PENDING = 32;
export const TIMEOUT_MS = 5000;

export function runtimeDirectory() {
  return join(process.env.XDG_RUNTIME_DIR || tmpdir(), `pi-agent-messaging-${process.getuid()}`);
}

async function privateDirectory(path) {
  await mkdir(path, { mode: 0o700, recursive: true });
  const stat = await lstat(path);
  if (!stat.isDirectory() || stat.uid !== process.getuid() || (stat.mode & 0o077)) {
    throw new Error('Messaging directory must be user-owned, private (0700), and not a symlink.');
  }
}

async function readPrivate(path) {
  const stat = await lstat(path);
  if (!stat.isFile() || stat.uid !== process.getuid() || (stat.mode & 0o077)) {
    throw new Error('Contact file must be user-owned, private (0600), and not a symlink.');
  }
  if (stat.size > 64 * 1024) throw new Error('Contact file is too large.');
  const text = await readFile(path, 'utf8');
  try { return JSON.parse(text); } catch { throw new Error('Invalid contact file JSON.'); }
}

function validContact(value) {
  return value && typeof value.session === 'string' && value.session.length <= 128 &&
    typeof value.socket === 'string' && value.socket.startsWith('/') &&
    typeof value.token === 'string' && /^[a-f0-9]{64}$/.test(value.token);
}

export async function identity(directory, session) {
  if (typeof session !== 'string' || !session || session.length > 128) throw new Error('Invalid session ID.');
  directory = resolve(directory);
  await privateDirectory(directory);
  const name = createHash('sha256').update(session).digest('hex').slice(0, 24);
  const path = join(directory, `${name}.json`);
  const socket = join(directory, `${name}.sock`);
  if (Buffer.byteLength(socket) > 100) throw new Error('Messaging directory path is too long for a Unix socket.');
  const fresh = { session, socket, token: randomBytes(32).toString('hex'), peers: [] };
  try {
    await writeFile(path, JSON.stringify(fresh), { mode: 0o600, flag: 'wx' });
  } catch (error) {
    if (error.code !== 'EEXIST') throw error;
  }
  const saved = await readPrivate(path);
  if (!validContact(saved) || saved.session !== session || saved.socket !== socket || !Array.isArray(saved.peers) ||
      !saved.peers.every(validContact)) throw new Error('Invalid stored messaging identity.');
  return { ...saved, path };
}

export async function linkPeer(self, contactPath) {
  const contact = await readPrivate(resolve(contactPath));
  if (!validContact(contact) || contact.session === self.session) throw new Error('Invalid peer contact.');
  const peer = { session: contact.session, socket: contact.socket, token: contact.token };
  const peers = [...self.peers.filter((item) => item.session !== peer.session), peer];
  // Persist only identity/link metadata, never pending messages or message contents.
  await writeFile(self.path, JSON.stringify({ session: self.session, socket: self.socket, token: self.token, peers }), { mode: 0o600 });
  self.peers = peers;
  return peer.session;
}

function sameSecret(actual, expected) {
  if (typeof actual !== 'string') return false;
  const a = Buffer.from(actual);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

function parseEnvelope(raw, self) {
  let message;
  try { message = JSON.parse(raw); } catch { throw new Error('Invalid JSON.'); }
  if (!message || message.version !== 1 || typeof message.id !== 'string' || !/^[a-f0-9-]{36}$/.test(message.id) ||
      typeof message.sender !== 'string' || message.recipient !== self.session ||
      typeof message.content !== 'string' || !message.content.trim()) throw new Error('Invalid message envelope.');
  if (!sameSecret(message.credential, self.token) || !self.peers.some((peer) => peer.session === message.sender)) {
    throw new Error('Sender is not linked or credential is invalid.');
  }
  return { version: 1, id: message.id, sender: message.sender, recipient: message.recipient, content: message.content };
}

export async function listen(self, admit, onError = () => {}) {
  const connections = new Set();
  const server = createServer((socket) => {
    connections.add(socket);
    socket.on('close', () => connections.delete(socket));
    socket.on('error', () => {});
    socket.setTimeout(TIMEOUT_MS, () => socket.destroy());
    let buffer = Buffer.alloc(0);
    let done = false;
    socket.on('data', (chunk) => {
      if (done) return;
      buffer = Buffer.concat([buffer, chunk]);
      const end = buffer.indexOf(10);
      if (buffer.length > MAX_BYTES || (end >= 0 && end !== buffer.length - 1)) {
        done = true;
        socket.end(JSON.stringify({ accepted: false, error: 'Message exceeds limit or has extra data.' }) + '\n');
        return;
      }
      if (end < 0) return;
      done = true;
      let response;
      try {
        const message = parseEnvelope(buffer.subarray(0, end).toString('utf8'), self);
        admit(message); // Synchronous validation/admission; never wait for a model response.
        response = { accepted: true, id: message.id };
      } catch (error) {
        response = { accepted: false, error: error.message };
      }
      socket.end(JSON.stringify(response) + '\n');
    });
  });
  server.maxConnections = MAX_PENDING;
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(self.socket, () => {
      server.removeListener('error', reject);
      resolve();
    });
  });
  server.on('error', () => onError('Messaging receiver error; delivery may be unavailable.'));
  // Do not unlink an existing socket on startup: another live session may own it.
  return async () => {
    for (const socket of connections) socket.destroy();
    await new Promise((resolve) => server.close(resolve));
  };
}

export function send(self, recipient, content, { signal, timeout = TIMEOUT_MS } = {}) {
  const peer = self.peers.find((item) => item.session === recipient);
  if (!peer) return Promise.reject(new Error('Recipient is not linked.'));
  if (typeof content !== 'string' || !content.trim()) return Promise.reject(new Error('Message must contain text.'));
  const id = randomUUID();
  const frame = JSON.stringify({ version: 1, id, sender: self.session, recipient, content, credential: peer.token }) + '\n';
  if (Buffer.byteLength(frame) > MAX_BYTES) return Promise.reject(new Error('Complete message exceeds 16 KiB.'));
  if (signal?.aborted) return Promise.reject(new Error('Send cancelled before connection.'));
  return new Promise((resolve, reject) => {
    const socket = createConnection(peer.socket);
    let response = '';
    let attempted = false;
    const uncertain = () => reject(new Error('Delivery unconfirmed; do not automatically retry.'));
    const cancel = () => { uncertain(); socket.destroy(); };
    const timer = setTimeout(cancel, timeout);
    signal?.addEventListener('abort', cancel, { once: true });
    socket.on('connect', () => { attempted = true; socket.write(frame); });
    socket.on('data', (chunk) => {
      response += chunk.toString('utf8');
      if (Buffer.byteLength(response) > MAX_BYTES) return cancel();
      if (!response.includes('\n')) return;
      try {
        const reply = JSON.parse(response.trim());
        if (reply.accepted === true && reply.id === id) resolve({ accepted: true, id });
        else if (reply.accepted === false && typeof reply.error === 'string') {
          // Do not reflect arbitrary peer text (which could contain secrets) into tool output.
          reject(new Error('Recipient rejected the message (invalid envelope/authentication or full inbox).'));
        } else uncertain();
      } catch { uncertain(); }
      socket.destroy();
    });
    socket.on('error', () => {
      if (attempted) uncertain();
      else reject(new Error('Recipient unavailable; connection failed before sending.'));
    });
    socket.on('close', () => {
      clearTimeout(timer);
      signal?.removeEventListener('abort', cancel);
      uncertain(); // No-op if a reply or error has already settled the promise.
    });
  });
}
