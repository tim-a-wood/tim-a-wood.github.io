#!/usr/bin/env node
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');

const REMOTE_DEBUGGING_PORT = 9226;
const CHROME_BINARY = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const DEFAULT_PROJECT_ID = 'ruined-gothic-calibration-gemini-20260402';
const DEFAULT_EDITOR_URL = 'http://127.0.0.1:8766/room-layout-editor.html';
const DEFAULT_ROOMS = ['RG-R1', 'RG-R2', 'RG-R3'];

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
    this.ws = new WebSocket(wsUrl);
    this.id = 0;
    this.pending = new Map();
    this.openPromise = new Promise((resolve, reject) => {
      this.ws.addEventListener('open', resolve, { once: true });
      this.ws.addEventListener('error', reject, { once: true });
    });
    this.ws.addEventListener('message', (event) => {
      const message = JSON.parse(event.data);
      if (!message.id) return;
      const slot = this.pending.get(message.id);
      if (!slot) return;
      this.pending.delete(message.id);
      if (message.error) slot.reject(new Error(message.error.message || 'CDP error'));
      else slot.resolve(message.result || {});
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

async function waitForEditorReady(client) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const result = await client.send('Runtime.evaluate', {
      expression: `(() => {
        const select = document.getElementById('roomSelect');
        return {
          hasQa: Boolean(window.__ROOM_WIZARD_QA__),
          optionCount: select ? select.options.length : 0,
          status: document.readyState,
        };
      })()`,
      returnByValue: true,
      awaitPromise: true,
    });
    const value = result.result.value || {};
    if (value.hasQa && value.optionCount > 0) return value;
    await delay(250);
  }
  throw new Error('Editor did not become ready');
}

async function selectRoomAndOpenResults(client, roomId) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const optionState = await client.send('Runtime.evaluate', {
      expression: `(() => {
        const select = document.getElementById('roomSelect');
        return {
          hasRoom: Boolean(select && Array.from(select.options).some((item) => item.value === ${JSON.stringify(roomId)})),
          options: select ? Array.from(select.options).map((item) => item.value) : [],
        };
      })()`,
      returnByValue: true,
      awaitPromise: true,
    });
    if (optionState.result.value?.hasRoom) break;
    await delay(250);
    if (attempt === 79) {
      throw new Error(`Room option never appeared for ${roomId}: ${JSON.stringify(optionState.result.value || {})}`);
    }
  }
  const result = await client.send('Runtime.evaluate', {
    expression: `(() => {
      const select = document.getElementById('roomSelect');
      if (!select) return { ok: false, error: 'room_select_missing' };
      const option = Array.from(select.options).find((item) => item.value === ${JSON.stringify(roomId)});
      if (!option) return { ok: false, error: 'room_option_missing' };
      select.value = option.value;
      select.dispatchEvent(new Event('change', { bubbles: true }));
      return window.__ROOM_WIZARD_QA__ ? window.__ROOM_WIZARD_QA__.applyResultsEnvironment(null) : { ok: false, error: 'qa_hook_missing' };
    })()`,
    returnByValue: true,
    awaitPromise: true,
  });
  const value = result.result.value || {};
  if (!value.ok) {
    throw new Error(`Failed to open Results for ${roomId}: ${JSON.stringify(value)}`);
  }
  return value;
}

async function captureFullPage(client, outputPath) {
  await client.send('Emulation.setDeviceMetricsOverride', {
    width: 1680,
    height: 2400,
    deviceScaleFactor: 1,
    mobile: false,
  });
  const layout = await client.send('Page.getLayoutMetrics');
  const contentSize = layout.contentSize || { width: 1680, height: 2400 };
  const screenshot = await client.send('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: true,
    clip: {
      x: 0,
      y: 0,
      width: Math.min(1680, Math.ceil(contentSize.width || 1680)),
      height: Math.ceil(contentSize.height || 2400),
      scale: 1,
    },
  });
  fs.writeFileSync(outputPath, Buffer.from(screenshot.data, 'base64'));
  return contentSize;
}

async function main() {
  const projectId = process.argv[2] || DEFAULT_PROJECT_ID;
  const rooms = process.argv.slice(3).length ? process.argv.slice(3) : DEFAULT_ROOMS;
  const editorUrl = new URL(DEFAULT_EDITOR_URL);
  editorUrl.searchParams.set('project_id', projectId);

  const outputDir = path.join(process.cwd(), 'artifacts', 'qa', 'room-results-calibration', projectId);
  fs.mkdirSync(outputDir, { recursive: true });

  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'mv-results-calibration-'));
  const chrome = spawn(CHROME_BINARY, [
    `--remote-debugging-port=${REMOTE_DEBUGGING_PORT}`,
    '--headless=new',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    '--hide-scrollbars',
    '--mute-audio',
    '--window-size=1680,2400',
    `--user-data-dir=${userDataDir}`,
    editorUrl.toString(),
  ], { stdio: 'ignore' });

  let client = null;
  try {
    const targets = await fetchJson(`http://127.0.0.1:${REMOTE_DEBUGGING_PORT}/json/list`);
    const target = targets.find((item) => item.url.includes('room-layout-editor.html')) || targets[0];
    client = new CdpClient(target.webSocketDebuggerUrl);
    await client.open();
    await client.send('Page.enable');
    await client.send('Runtime.enable');

    await waitForEditorReady(client);

    const summary = {
      project_id: projectId,
      generated_at: new Date().toISOString(),
      rooms: [],
    };

    for (const roomId of rooms) {
      const details = await selectRoomAndOpenResults(client, roomId);
      await delay(1000);
      const outputPath = path.join(outputDir, `${roomId}.png`);
      const contentSize = await captureFullPage(client, outputPath);
      summary.rooms.push({
        room_id: roomId,
        screenshot: outputPath,
        details,
        content_width: contentSize.width,
        content_height: contentSize.height,
      });
    }

    fs.writeFileSync(path.join(outputDir, 'summary.json'), JSON.stringify(summary, null, 2));
    process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
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
