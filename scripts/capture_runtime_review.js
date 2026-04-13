#!/usr/bin/env node
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');

/** Node 21+ exposes global WebSocket; older releases need the optional `ws` package. */
const WebSocketCtor = (() => {
  if (typeof globalThis.WebSocket === 'function') return globalThis.WebSocket;
  try {
    return require('ws');
  } catch (_) {
    return null;
  }
})();
if (!WebSocketCtor) {
  process.stderr.write(
    'capture_runtime_review.js: need Node.js 21+ (global WebSocket) or run `npm install ws` in the repo.\n',
  );
  process.exit(1);
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchJson(url, retries = 40) {
  let lastError;
  for (let attempt = 0; attempt < retries; attempt += 1) {
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      lastError = error;
      await delay(250);
    }
  }
  throw lastError;
}

class CdpClient {
  constructor(wsUrl) {
    this.ws = new WebSocketCtor(wsUrl);
    this.id = 0;
    this.pending = new Map();
    this.openPromise = new Promise((resolve, reject) => {
      this.ws.addEventListener('open', resolve, { once: true });
      this.ws.addEventListener('error', reject, { once: true });
    });
    this.ws.addEventListener('message', (event) => {
      const message = JSON.parse(event.data);
      if (!message.id) return;
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      if (message.error) {
        pending.reject(new Error(message.error.message || 'CDP error'));
      } else {
        pending.resolve(message.result || {});
      }
    });
  }

  async open() {
    await this.openPromise;
  }

  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async close() {
    if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
      this.ws.close();
      await delay(100);
    }
  }
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith('--')) continue;
    const key = token.slice(2);
    const next = argv[index + 1];
    if (next && !next.startsWith('--')) {
      args[key] = next;
      index += 1;
    } else {
      args[key] = 'true';
    }
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const browser = args.browser;
  const url = args.url;
  const output = args.output;
  const width = Number(args.width || 1600);
  const height = Number(args.height || 1200);
  const timeoutMs = Number(args.timeout || 30000);
  const port = Number(args.port || 9236);

  if (!browser || !url || !output) {
    throw new Error('Usage: capture_runtime_review.js --browser <path> --url <url> --output <png> [--width N --height N --timeout MS]');
  }

  fs.mkdirSync(path.dirname(output), { recursive: true });
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'mv-runtime-review-'));
  const chrome = spawn(browser, [
    `--remote-debugging-port=${port}`,
    '--headless=new',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    '--hide-scrollbars',
    '--mute-audio',
    `--window-size=${width},${height}`,
    `--user-data-dir=${userDataDir}`,
    url,
  ], { stdio: 'ignore' });

  let client = null;
  try {
    await delay(800);
    const targets = await fetchJson(`http://127.0.0.1:${port}/json/list`);
    const target = targets.find((item) => item.url.includes('runtime-capture.html')) || targets[0];
    if (!target?.webSocketDebuggerUrl) {
      throw new Error('Runtime capture target not available');
    }

    client = new CdpClient(target.webSocketDebuggerUrl);
    await client.open();
    await client.send('Page.enable');
    await client.send('Runtime.enable');
    await client.send('Emulation.setDeviceMetricsOverride', {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: false,
    });

    const start = Date.now();
    let lastState = null;
    while ((Date.now() - start) < timeoutMs) {
      const result = await client.send('Runtime.evaluate', {
        expression: `(() => {
          const iframe = document.querySelector('#preview');
          const win = iframe && iframe.contentWindow;
          const doc = iframe && iframe.contentDocument;
          const canvas = doc && doc.querySelector('canvas');
          const rect = canvas ? canvas.getBoundingClientRect() : null;
          return {
            bootState: win ? win.__ASHEN_HOLLOW_BOOT_STATE || null : null,
            bootError: win ? win.__ASHEN_HOLLOW_LAST_BOOT_ERROR || null : null,
            pageBoot: win ? win.__ASHEN_HOLLOW_PAGE_BOOT_STATE || null : null,
            canvasCount: doc ? doc.querySelectorAll('canvas').length : 0,
            canvasVisible: Boolean(rect && rect.width > 0 && rect.height > 0),
          };
        })()`,
        returnByValue: true,
        awaitPromise: true,
      });
      lastState = result.result.value || null;
      if (
        lastState
        && !lastState.bootError
        && lastState.canvasCount >= 1
        && lastState.canvasVisible
        && typeof lastState.bootState === 'string'
        && lastState.bootState.includes('| live')
      ) {
        await delay(750);
        const screenshot = await client.send('Page.captureScreenshot', {
          format: 'png',
          fromSurface: true,
        });
        fs.writeFileSync(output, Buffer.from(screenshot.data, 'base64'));
        return;
      }
      await delay(250);
    }

    throw new Error(`Runtime preview did not become ready: ${JSON.stringify(lastState)}`);
  } finally {
    if (client) await client.close();
    chrome.kill('SIGKILL');
  }
}

main().catch((error) => {
  const message = error && error.stack ? error.stack : String(error);
  process.stderr.write(`${message}\n`);
  process.exitCode = 1;
});
