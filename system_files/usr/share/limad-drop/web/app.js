const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const app = $('#app');
const toastBox = $('#toast');

let adminToken = '';
let deviceToken = localStorage.getItem('limadDropDeviceToken') || '';
let state = null;
let refreshTimer = null;
let lastPairToken = '';
let activeTransferController = null;
let refreshFailures = 0;
const pairFromUrl = new URLSearchParams(location.search).get('pair') || '';

if (location.hash.startsWith('#admin=')) {
  adminToken = decodeURIComponent(location.hash.slice(7));
  history.replaceState(null, '', location.pathname);
}

const fmt = (value) => {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let index = 0;
  let amount = Number(value) || 0;
  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024;
    index += 1;
  }
  return `${amount >= 10 || index === 0 ? amount.toFixed(0) : amount.toFixed(1)} ${units[index]}`;
};
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
}[char]));
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const fmtRate = (value) => `${fmt(value)}/s`;
const fmtEta = (seconds) => !Number.isFinite(seconds) || seconds < 0
  ? '–'
  : seconds < 60
    ? `${Math.ceil(seconds)} Sek.`
    : `${Math.floor(seconds / 60)} Min. ${Math.ceil(seconds % 60)} Sek.`;

function toast(message, bad = false) {
  toastBox.textContent = message;
  toastBox.classList.toggle('error', bad);
  toastBox.classList.add('show');
  setTimeout(() => toastBox.classList.remove('show'), 2800);
}

function authHeaders(extra = {}) {
  const headers = new Headers(extra);
  if (adminToken) headers.set('X-LiMaD-Admin', adminToken);
  else if (deviceToken) headers.set('Authorization', `Bearer ${deviceToken}`);
  return headers;
}

async function api(path, options = {}) {
  const method = String(options.method || 'GET').toUpperCase();
  const retries = options.retries ?? (method === 'GET' ? 2 : 0);
  const headers = authHeaders(options.headers || {});
  const request = { ...options, method, headers };
  delete request.json;
  delete request.retries;
  if (options.json !== undefined) {
    headers.set('Content-Type', 'application/json');
    request.body = JSON.stringify(options.json);
  }

  let lastError;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    let timeoutController = null;
    let timeoutId = null;
    try {
      if (!request.signal && method === 'GET') {
        timeoutController = new AbortController();
        request.signal = timeoutController.signal;
        timeoutId = setTimeout(() => timeoutController.abort(), 9000);
      }
      const response = await fetch(path, request);
      if (timeoutId) clearTimeout(timeoutId);
      const type = response.headers.get('content-type') || '';
      const data = type.includes('json') ? await response.json() : await response.blob();
      if (!response.ok) {
        const error = new Error(data?.error || `HTTP ${response.status}`);
        error.status = response.status;
        throw error;
      }
      return data;
    } catch (error) {
      if (timeoutId) clearTimeout(timeoutId);
      lastError = error;
      if (options.signal?.aborted || error?.name === 'AbortError' && options.signal) throw error;
      const retryable = error instanceof TypeError || error?.name === 'AbortError' || [408, 429, 502, 503, 504].includes(error?.status);
      if (!retryable || attempt >= retries) throw error;
      await sleep(Math.min(3200, 350 * (2 ** attempt)) + Math.random() * 180);
      if (timeoutController) delete request.signal;
    }
  }
  throw lastError || new Error('Netzwerkfehler');
}

function progressMarkup() {
  return `<div id="uploadProgress" class="transfer-progress hidden">
    <div class="progress-head">
      <div><strong data-progress-title>Übertragung wird vorbereitet …</strong><span data-progress-state>Startet sofort</span></div>
      <b data-progress-percent>0%</b>
    </div>
    <div class="progress"><span></span></div>
    <div class="progress-details"><span data-progress-bytes>0 B von 0 B</span><span data-progress-rate>0 B/s</span><span data-progress-eta>Restzeit –</span></div>
    <button type="button" class="progress-cancel" data-progress-cancel>Abbrechen</button>
  </div>`;
}

function setProgress(box, info) {
  if (!box) return;
  box.classList.remove('hidden');
  const total = Math.max(0, Number(info.total) || 0);
  const received = Math.max(0, Number(info.received) || 0);
  const percent = total ? Math.min(100, received / total * 100) : 0;
  const labels = {
    preparing: 'Wird vorbereitet …', uploading: 'Wird übertragen …', downloading: 'Wird heruntergeladen …',
    verifying: 'Prüfsumme wird kontrolliert …', done: 'Übertragung abgeschlossen',
    cancelled: 'Übertragung abgebrochen', error: 'Übertragung fehlgeschlagen'
  };
  $('[data-progress-title]', box).textContent = info.file || 'Dateiübertragung';
  $('[data-progress-state]', box).textContent = labels[info.phase] || info.phase || '';
  $('[data-progress-percent]', box).textContent = `${Math.round(percent)}%`;
  $('[data-progress-bytes]', box).textContent = `${fmt(received)} von ${fmt(total)}`;
  $('[data-progress-rate]', box).textContent = info.rate ? fmtRate(info.rate) : '0 B/s';
  $('[data-progress-eta]', box).textContent = `Restzeit ${info.eta === undefined ? '–' : fmtEta(info.eta)}`;
  $('.progress span', box).style.width = `${percent}%`;
  box.dataset.phase = info.phase || '';
  const cancel = $('[data-progress-cancel]', box);
  cancel.disabled = ['done', 'error', 'cancelled'].includes(info.phase);
  cancel.textContent = info.phase === 'verifying' ? 'Prüfung läuft …' : 'Abbrechen';
}

function busyUi(busy) {
  const pick = $('#pick');
  const drop = $('#dropzone');
  if (pick) {
    pick.disabled = busy;
    pick.textContent = busy ? 'Übertragung läuft …' : 'Dateien auswählen';
  }
  if (drop) drop.classList.toggle('busy', busy);
}

function uploadBodyXHR(path, body, baseOffset, totalSize, fileName, onProgress, signal) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const started = performance.now();
    let settled = false;
    let lastActivity = Date.now();
    let watchdog = null;

    const cleanup = () => {
      if (watchdog) clearInterval(watchdog);
      if (signal) signal.removeEventListener('abort', abortFromSignal);
    };
    const fail = (error) => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(error);
    };
    const abortFromSignal = () => {
      xhr.abort();
      fail(new DOMException('Übertragung abgebrochen', 'AbortError'));
    };

    xhr.open('PUT', path, true);
    authHeaders({ 'Content-Type': 'application/octet-stream' }).forEach((value, key) => {
      xhr.setRequestHeader(key, value);
    });
    xhr.setRequestHeader('X-LiMaD-Upload-Mode', 'stream');
    xhr.responseType = 'text';

    xhr.upload.onprogress = (event) => {
      lastActivity = Date.now();
      const current = Math.min(totalSize, baseOffset + Number(event.loaded || 0));
      const elapsed = Math.max(.25, (performance.now() - started) / 1000);
      const rate = Math.max(0, (current - baseOffset) / elapsed);
      const remaining = Math.max(0, totalSize - current);
      onProgress({
        phase: 'uploading', file: fileName, received: current, total: totalSize,
        rate, eta: rate ? remaining / rate : undefined
      });
    };

    xhr.onload = () => {
      if (settled) return;
      lastActivity = Date.now();
      let data = {};
      try { data = xhr.responseText ? JSON.parse(xhr.responseText) : {}; }
      catch { return fail(new Error(`Ungültige LiDrop-Antwort (HTTP ${xhr.status})`)); }
      if (xhr.status < 200 || xhr.status >= 300) {
        const error = new Error(data?.error || `HTTP ${xhr.status}`);
        error.status = xhr.status;
        return fail(error);
      }
      settled = true;
      cleanup();
      resolve(data);
    };
    xhr.onerror = () => fail(new TypeError('Netzwerkverbindung wurde unterbrochen'));
    xhr.ontimeout = () => fail(new Error('Die Übertragung hat zu lange nicht geantwortet'));
    xhr.onabort = () => {
      if (signal?.aborted) fail(new DOMException('Übertragung abgebrochen', 'AbortError'));
      else fail(new Error('Die Übertragung wurde wegen Stillstand neu gestartet'));
    };

    if (signal) {
      if (signal.aborted) return abortFromSignal();
      signal.addEventListener('abort', abortFromSignal, { once: true });
    }

    // XHR handles a File/Blob as a streamed request body in WebKitGTK. A
    // watchdog is still required because fetch/PUT could otherwise wait
    // forever after a network interruption without throwing an exception.
    watchdog = setInterval(() => {
      if (!settled && Date.now() - lastActivity > 45000) xhr.abort();
    }, 2000);
    xhr.send(body);
  });
}

async function uploadFile(file, direction, deviceId = '', onProgress = () => {}, signal) {
  onProgress({ phase: 'preparing', file: file.name, received: 0, total: file.size, rate: 0 });
  let transfer = await api('/api/upload/init', {
    method: 'POST', signal,
    json: { direction, deviceId, name: file.name, size: file.size, lastModified: file.lastModified }
  });
  let offset = Number(transfer.received) || 0;
  let attempts = 0;
  onProgress({ phase: 'uploading', file: file.name, received: offset, total: file.size, rate: 0 });

  while (offset < file.size) {
    if (signal?.aborted) throw new DOMException('Übertragung abgebrochen', 'AbortError');
    try {
      // Send the complete remaining part in one streamed XHR request. The old
      // implementation issued one fetch request per 256 KiB block; WebKitGTK
      // could stop before the second Blob request and remain at exactly 256 KiB.
      const result = await uploadBodyXHR(
        `/api/upload/${transfer.id}?offset=${offset}`,
        file.slice(offset), offset, file.size, file.name, onProgress, signal
      );
      const nextOffset = Number(result.received);
      if (!Number.isFinite(nextOffset) || nextOffset <= offset) {
        throw new Error('Der Empfänger hat keinen weiteren Dateiblock bestätigt');
      }
      offset = Math.min(file.size, nextOffset);
      attempts = 0;
    } catch (error) {
      if (signal?.aborted || error?.name === 'AbortError') throw error;
      attempts += 1;
      if (attempts >= 8) throw error;
      await sleep(Math.min(5000, 500 * (2 ** (attempts - 1))) + Math.random() * 220);
      transfer = await api('/api/upload/init', {
        method: 'POST', signal,
        json: { direction, deviceId, name: file.name, size: file.size, lastModified: file.lastModified }
      });
      offset = Number(transfer.received) || 0;
      onProgress({ phase: 'uploading', file: file.name, received: offset, total: file.size, rate: 0 });
    }
  }

  onProgress({ phase: 'verifying', file: file.name, received: file.size, total: file.size, rate: 0 });
  await api(`/api/upload/${transfer.id}/complete`, { method: 'POST', signal });
  onProgress({ phase: 'done', file: file.name, received: file.size, total: file.size, rate: 0, eta: 0 });
  return transfer.id;
}

async function runUploadQueue(files, direction, deviceId, after) {
  if (!files.length || activeTransferController) return;
  const box = $('#uploadProgress');
  activeTransferController = new AbortController();
  const controller = activeTransferController;
  busyUi(true);
  $('[data-progress-cancel]', box).onclick = () => controller.abort();
  try {
    for (const file of files) {
      await uploadFile(file, direction, deviceId, (info) => setProgress(box, info), controller.signal);
      toast(`${file.name} wurde vollständig übertragen.`);
      await sleep(450);
    }
  } catch (error) {
    if (error?.name === 'AbortError') {
      setProgress(box, { phase: 'cancelled', file: 'Übertragung', received: 0, total: 0 });
      toast('Übertragung wurde abgebrochen.');
    } else {
      setProgress(box, { phase: 'error', file: 'Übertragung', received: 0, total: 0 });
      toast(error.message || String(error), true);
    }
  } finally {
    activeTransferController = null;
    busyUi(false);
    const input = $('#files');
    if (input) input.value = '';
    await after(false);
    setTimeout(() => {
      if (!activeTransferController) box?.classList.add('hidden');
    }, 1800);
  }
}

function topbar(sub = 'Direkt im lokalen WLAN') {
  return `<div class="topbar"><div class="brand"><div class="brand-mark">⇅</div><div><h1>LiDrop</h1><p>${esc(sub)}</p></div></div><div class="status"><span class="dot"></span><span>Netzwerk verbunden</span></div></div>`;
}

function adminView() {
  app.innerHTML = `<div class="desktop-shell">
    <header class="topbar">
      <div class="brand"><div class="brand-mark">⇅</div><div><h1>LiDrop</h1><small>0.12.0-preview8</small></div></div>
      <div class="top-actions">
        <div id="networkStatus" class="network-pill"><span class="dot"></span><span>Verbunden</span></div>
        <button id="openFolderTop" class="soft-button">LiDrop-Ordner</button>
        <button id="settingsBtn" class="icon-btn ghost" title="Einstellungen">⚙</button>
      </div>
    </header>

    <main class="clean-workspace">
      <section class="share-card">
        <div class="share-heading">
          <div><h2>Senden & Empfangen</h2><p>Gerät antippen, Datei auswählen, fertig.</p></div>
          <button id="pairBtn" class="soft-button">＋ Gerät</button>
        </div>
        <div id="connectedDevices" class="device-bubbles"></div>
        <select id="target" class="sr-only" aria-label="Zielgerät"><option value="">Kein Ziel</option></select>
        <div id="dropzone" class="dropzone clean-drop">
          <div class="drop-icon">⇧</div>
          <strong>Dateien senden</strong>
          <span id="dropHint">Zuerst ein Gerät auswählen</span>
          <button id="pick" class="primary">Dateien auswählen</button>
          <input id="files" class="hidden" type="file" multiple>
        </div>
        ${progressMarkup()}
      </section>

      <section class="transfers-card">
        <div class="section-title main-title">
          <div><h2>Übertragungen</h2><span id="transferSummary" class="section-subtitle">Keine laufende Übertragung</span></div>
          <button id="openFolderBtn" class="folder-button">Ordner öffnen</button>
        </div>
        <div id="activeTransfers" class="transfer-list clean-list"></div>
        <div class="finished-heading"><h3>Fertig</h3><button id="clearHistoryBtn" class="ghost compact-action">Leeren</button></div>
        <div id="finishedTransfers" class="transfer-list clean-list"></div>
      </section>
    </main>

    <dialog id="pairDialog" class="modal">
      <div class="modal-head"><h2>Gerät verbinden</h2><button class="close-btn ghost" data-close-dialog="pairDialog">×</button></div>
      <div class="modal-body">
        <div class="pairing"><img id="qr" class="qr" alt="LiDrop QR-Code"><div><div id="pairCode" class="code">------</div><div id="address" class="address"></div><p class="fine">Für Smartphone oder zweiten LiMaD-Rechner.</p></div></div>
        <div class="peer-connect"><div class="section-title"><h3>LiMaD OS zu LiMaD OS</h3><button id="discoverPeersBtn" class="ghost compact-action">Rechner suchen</button></div><div id="discoveredPeers" class="discovered-peers"></div><label>Adresse des anderen Rechners<input id="peerAddress" type="text" placeholder="http://192.168.1.50:47777"></label><label>Code vom anderen Rechner<input id="peerCodeInput" type="text" inputmode="numeric" placeholder="000 000" maxlength="7"></label><button id="connectPeerBtn" class="primary">Beide Rechner verbinden</button><p class="fine">Einmal koppeln. Danach können beide LiMaD-OS-Rechner Dateien direkt senden.</p></div>
      </div>
    </dialog>

    <dialog id="settingsDialog" class="modal wide-modal">
      <div class="modal-head"><h2>Einstellungen</h2><button class="close-btn ghost" data-close-dialog="settingsDialog">×</button></div>
      <div class="modal-body settings-grid">
        <section class="settings-block"><div class="section-title"><h3>Smartphones und Browser</h3><button id="clearOfflineBtn" class="ghost compact-action">Offline löschen</button></div><div id="devices" class="list"></div></section>
        <section class="settings-block"><div class="section-title"><h3>LiMaD-OS-Rechner</h3></div><div id="peers" class="list"></div></section>
        <details class="settings-block advanced-block"><summary>AirDrop-Kompatibilität</summary><div class="section-title"><span></span><button id="airdropRecheck" class="ghost">Neu prüfen</button></div><div id="airdropState" class="airdrop-state"></div><div class="airdrop-controls"><label class="toggle-row"><span class="switch"><input id="airdropEnabled" type="checkbox"><span class="slider"></span></span><span>AirDrop aktivieren</span></label><select id="airdropVisibility"><option value="off">Aus</option><option value="contacts">Bekannte Geräte</option><option value="everyone10">Alle · 10 Minuten</option></select><button id="airdropApply">Übernehmen</button></div></details>
      </div>
    </dialog>
  </div>`;
  bindAdmin();
  refreshAdmin(false);
}

function bindAdmin() {
  const input = $('#files');
  const drop = $('#dropzone');
  $('#pick').onclick = () => { if (!activeTransferController) input.click(); };
  drop.onclick = (event) => {
    if (event.target.closest('button')) return;
    if (!activeTransferController) input.click();
  };
  input.onchange = () => sendFiles([...input.files]);
  ['dragenter', 'dragover'].forEach((name) => drop.addEventListener(name, (event) => {
    event.preventDefault();
    if (!activeTransferController) drop.classList.add('drag');
  }));
  ['dragleave', 'drop'].forEach((name) => drop.addEventListener(name, (event) => {
    event.preventDefault();
    drop.classList.remove('drag');
  }));
  drop.addEventListener('drop', (event) => {
    if (!activeTransferController) sendFiles([...event.dataTransfer.files]);
  });
  $('#pairBtn').onclick = () => $('#pairDialog').showModal();
  $('#discoverPeersBtn').onclick = discoverPeers;
  $('#connectPeerBtn').onclick = connectPeer;
  $('#settingsBtn').onclick = () => $('#settingsDialog').showModal();
  $('#openFolderBtn').onclick = openDestination;
  $('#openFolderTop').onclick = openDestination;
  $('#clearOfflineBtn').onclick = () => bulkDeleteDevices('offline');
  $('#clearHistoryBtn').onclick = () => bulkDeleteTransfers('finished');
  $$('[data-close-dialog]').forEach((button) => button.onclick = () => $(`#${button.dataset.closeDialog}`).close());
  $('#airdropApply').onclick = applyAirDrop;
  $('#airdropRecheck').onclick = async () => {
    const button = $('#airdropRecheck');
    button.disabled = true;
    try {
      const result = await api('/api/admin/airdrop', { method: 'POST', json: { enabled: $('#airdropEnabled').checked, visibility: $('#airdropVisibility').value } });
      renderAirDrop(result.airdrop);
      toast('AirDrop wurde neu geprüft.');
    } catch (error) { toast(error.message, true); }
    finally { button.disabled = false; }
  };
}

async function sendFiles(files) {
  if (!files.length) return;
  const target = $('#target').value;
  if (!target) return toast('Bitte zuerst ein Gerät auswählen.', true);
  await runUploadQueue(files, 'outbound', target, refreshAdmin);
}

function scheduleRefresh(delay) {
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => refreshAdmin(true), delay);
}

function markNetwork(ok) {
  const pill = $('#networkStatus');
  if (!pill) return;
  pill.classList.toggle('offline', !ok);
  $('span:last-child', pill).textContent = ok ? 'Verbunden' : 'Wird verbunden';
}

async function refreshAdmin(silent = true) {
  let delay = 1700;
  try {
    const next = await api('/api/admin/state');
    state = next;
    refreshFailures = 0;
    markNetwork(true);
    renderAdmin(next);
    delay = next.transfers.some((item) => ['uploading', 'sending'].includes(item.status)) ? 550 : 1600;
    if (next.pairing.token !== lastPairToken) {
      lastPairToken = next.pairing.token;
      const qr = await api('/api/admin/qr');
      const image = $('#qr');
      const old = image.src;
      if (old.startsWith('blob:')) URL.revokeObjectURL(old);
      image.src = URL.createObjectURL(qr);
    }
  } catch (error) {
    refreshFailures += 1;
    markNetwork(false);
    if (!silent || refreshFailures === 1) toast('LiDrop verbindet sich neu.', true);
    delay = Math.min(15000, 1200 * (2 ** Math.min(refreshFailures, 4)));
  } finally {
    scheduleRefresh(delay);
  }
}

function transferProgress(transfer) {
  if (!['uploading', 'sending'].includes(transfer.status)) return '';
  const percent = transfer.size ? Math.min(100, (Number(transfer.received) || 0) / transfer.size * 100) : 0;
  return `<div class="inline-progress"><div class="progress"><span style="width:${percent}%"></span></div><span>${Math.round(percent)}% · ${fmt(transfer.received)} / ${fmt(transfer.size)}</span></div>`;
}

function renderAirDrop(airdrop) {
  const box = $('#airdropState');
  const enabled = $('#airdropEnabled');
  const visibility = $('#airdropVisibility');
  const apply = $('#airdropApply');
  if (!box) return;
  const available = Boolean(airdrop.available);
  enabled.checked = available && Boolean(airdrop.enabled);
  enabled.disabled = !available;
  visibility.value = available ? (airdrop.visibility || 'off') : 'off';
  visibility.disabled = !available || !enabled.checked;
  apply.disabled = !available;
  enabled.onchange = () => {
    visibility.disabled = !enabled.checked;
    if (!enabled.checked) visibility.value = 'off';
  };
  box.innerHTML = `<div class="airdrop-badge ${available ? 'ready' : 'preview'}">${available ? 'Bereit' : 'Nicht verfügbar'}</div><p>${esc(airdrop.message || 'Status wird geprüft …')}</p>`;
}

async function applyAirDrop() {
  const button = $('#airdropApply');
  if (button.disabled) return;
  button.disabled = true;
  try {
    const result = await api('/api/admin/airdrop', { method: 'POST', json: { enabled: $('#airdropEnabled').checked, visibility: $('#airdropVisibility').value } });
    renderAirDrop(result.airdrop);
    toast('Einstellung übernommen.');
  } catch (error) { toast(error.message, true); }
  finally { button.disabled = false; }
}

function allTargets(current = state) {
  const devices = (current?.devices || []).map((device) => ({ ...device, target_id: device.id, kind: 'device' }));
  const peers = (current?.peers || []).map((peer) => ({ ...peer, id: peer.target_id || `peer:${peer.id}`, kind: 'computer' }));
  return [...peers, ...devices];
}

async function discoverPeers() {
  const button = $('#discoverPeersBtn');
  button.disabled = true;
  $('#discoveredPeers').innerHTML = '<div class="empty">Suche im lokalen Netzwerk …</div>';
  try {
    const result = await api('/api/admin/peer/discover', { method: 'POST' });
    const peers = result.peers || [];
    $('#discoveredPeers').innerHTML = peers.length ? peers.map((peer) => `<button type="button" class="discovered-peer" data-peer-address="${esc(peer.address)}"><strong>${esc(peer.name)}</strong><span>${esc(peer.address)}</span></button>`).join('') : '<div class="empty">Kein weiterer LiMaD-Rechner gefunden. Adresse kann manuell eingetragen werden.</div>';
    $$('[data-peer-address]').forEach((item) => item.onclick = () => { $('#peerAddress').value = item.dataset.peerAddress; });
  } catch (error) { toast(error.message, true); }
  finally { button.disabled = false; }
}

async function connectPeer() {
  const button = $('#connectPeerBtn');
  const address = $('#peerAddress').value.trim();
  const code = $('#peerCodeInput').value.trim();
  if (!address || !code) return toast('Adresse und Code des anderen Rechners eingeben.', true);
  button.disabled = true;
  button.textContent = 'Rechner werden verbunden …';
  try {
    const result = await api('/api/admin/peer/connect', { method: 'POST', json: { address, code } });
    toast(`${result.peer?.name || 'LiMaD-Rechner'} wurde verbunden.`);
    $('#peerCodeInput').value = '';
    $('#pairDialog').close();
    await refreshAdmin(false);
  } catch (error) { toast(error.message, true); }
  finally { button.disabled = false; button.textContent = 'Beide Rechner verbinden'; }
}

function isRecentlySeen(device) {
  const stamp = Date.parse(device.last_seen);
  return Number.isFinite(stamp) && Date.now() - stamp < 45000;
}

function deviceBubble(device, selected) {
  const online = device.kind === 'computer' ? true : isRecentlySeen(device);
  const initial = esc((device.name || '?').trim().slice(0, 1).toUpperCase());
  return `<button class="device-bubble ${selected ? 'selected' : ''} ${online ? '' : 'offline-device'}" data-select-device="${device.id}"><span class="device-avatar">${initial}</span><strong>${esc(device.name)}</strong><small>${device.kind === 'computer' ? 'LiMaD OS' : online ? 'Bereit' : 'Offline'}</small></button>`;
}

function statusLabel(status) {
  return ({ uploading: 'Wird vorbereitet', sending: 'Wird gesendet', accepted: 'Empfangen', rejected: 'Abgelehnt', ready: 'Bereit zum Abholen', downloaded: 'Gesendet', revoked: 'Widerrufen', error: 'Fehler', cancelled: 'Abgebrochen', pending: 'Wartet', draft: 'Ziel wählen' })[status] || status;
}

function transferRow(transfer) {
  const done = ['accepted', 'downloaded'].includes(transfer.status);
  const failed = ['rejected', 'revoked', 'error', 'cancelled'].includes(transfer.status);
  const direction = transfer.direction === 'inbound' ? '↓' : '↑';
  return `<div class="transfer-row clean-transfer"><div class="file-icon">${direction}</div><div class="transfer-copy"><div class="item-title">${esc(transfer.filename)}</div><div class="item-meta">${fmt(transfer.size)} · ${esc(transfer.device_name || (transfer.direction === 'inbound' ? 'Empfangen' : 'LiMaD-PC'))}</div>${transferProgress(transfer)}</div><span class="status-text ${done ? 'good' : failed ? 'bad' : ''}">${statusLabel(transfer.status)}</span><button class="row-delete ghost" data-delete-transfer="${transfer.id}" title="Entfernen">×</button></div>`;
}

function outboundRow(transfer) {
  const options = allTargets(state).map((device) => `<option value="${device.id}" ${device.id === transfer.device_id ? 'selected' : ''}>${esc(device.name)}</option>`).join('');
  return `<div class="transfer-row clean-transfer"><div class="file-icon">↑</div><div class="transfer-copy"><div class="item-title">${esc(transfer.filename)}</div><div class="item-meta">${fmt(transfer.size)}</div></div><select data-target-transfer="${transfer.id}"><option value="">Gerät wählen</option>${options}</select><button class="row-delete ghost" data-delete-transfer="${transfer.id}" title="Entfernen">×</button></div>`;
}

function renderAdmin(current) {
  renderAirDrop(current.airdrop || {});
  $('#pairCode').textContent = `${current.pairing.code.slice(0, 3)} ${current.pairing.code.slice(3)}`;
  $('#address').textContent = current.pairing.address;

  const target = $('#target');
  const selected = target.value;
  const targets = allTargets(current);
  target.innerHTML = '<option value="">Kein Ziel</option>' + targets.map((device) => `<option value="${device.id}">${esc(device.name)}</option>`).join('');
  target.value = targets.some((device) => device.id === selected) ? selected : '';

  const sortedDevices = [...targets].sort((a, b) => Number(isRecentlySeen(b)) - Number(isRecentlySeen(a)) || String(b.last_seen).localeCompare(String(a.last_seen)));
  $('#connectedDevices').innerHTML = sortedDevices.length
    ? sortedDevices.map((device) => deviceBubble(device, device.id === target.value)).join('')
    : '<button class="empty-device" id="emptyPairButton"><span>＋</span><strong>Gerät verbinden</strong></button>';
  $$('[data-select-device]').forEach((button) => button.onclick = () => {
    target.value = button.dataset.selectDevice;
    $('#dropHint').textContent = `Senden an ${allTargets(state).find((device) => device.id === target.value)?.name || 'Gerät'}`;
    renderAdmin(state);
  });
  const emptyPair = $('#emptyPairButton');
  if (emptyPair) emptyPair.onclick = () => $('#pairDialog').showModal();
  const selectedName = targets.find((device) => device.id === target.value)?.name;
  $('#dropHint').textContent = selectedName ? `Senden an ${selectedName}` : 'Zuerst ein Gerät auswählen';

  $('#devices').innerHTML = current.devices.length ? current.devices.map(deviceCard).join('') : '<div class="empty">Noch kein Smartphone oder Browser gekoppelt.</div>';
  $$('[data-device]').forEach(bindDevice);
  $('#peers').innerHTML = current.peers?.length ? current.peers.map(peerCard).join('') : '<div class="empty">Noch kein zweiter LiMaD-OS-Rechner gekoppelt.</div>';
  $$('[data-peer]').forEach(bindPeer);

  const active = current.transfers.filter((transfer) => ['uploading', 'sending', 'pending', 'draft', 'ready'].includes(transfer.status));
  $('#activeTransfers').innerHTML = active.length ? active.map((transfer) => transfer.status === 'draft' ? outboundRow(transfer) : transferRow(transfer)).join('') : '<div class="empty clean-empty">Bereit für die nächste Übertragung.</div>';
  $('#transferSummary').textContent = active.length ? `${active.length} aktiv` : 'Keine laufende Übertragung';
  $$('[data-target-transfer]').forEach((select) => select.onchange = () => setTarget(select.dataset.targetTransfer, select.value));

  const finished = current.transfers.filter((transfer) => !['uploading', 'sending', 'pending', 'draft', 'ready'].includes(transfer.status)).slice(0, 10);
  $('#finishedTransfers').innerHTML = finished.length ? finished.map(transferRow).join('') : '<div class="empty clean-empty">Noch keine fertige Übertragung.</div>';
  $$('[data-delete-transfer]').forEach((button) => button.onclick = () => deleteTransfer(button.dataset.deleteTransfer));
}

function deviceCard(device) {
  return `<div class="item device-setting" data-device="${device.id}"><div><div class="item-title">${esc(device.name)}</div><div class="item-meta">Dateien werden automatisch angenommen · ${isRecentlySeen(device) ? 'Verbunden' : 'Offline'}</div></div><button class="danger" data-remove>Entfernen</button></div>`;
}

function bindDevice(element) {
  const id = element.dataset.device;
  $('[data-remove]', element).onclick = () => removeDevice(id);
}

function peerCard(peer) {
  return `<div class="item device-setting" data-peer="${peer.id}"><div><div class="item-title">${esc(peer.name)}</div><div class="item-meta">Direkter LiMaD-OS-Dateiversand · ${esc(peer.base_url)}</div></div><button class="danger" data-remove-peer>Entfernen</button></div>`;
}

function bindPeer(element) {
  const id = element.dataset.peer;
  $('[data-remove-peer]', element).onclick = () => removePeer(id);
}

async function removePeer(id) {
  if (!confirm('Diesen LiMaD-OS-Rechner entfernen?')) return;
  try {
    await api(`/api/admin/peer/${id}`, { method: 'DELETE' });
    toast('LiMaD-Rechner entfernt.');
    await refreshAdmin(false);
  } catch (error) { toast(error.message, true); }
}

async function openDestination() {
  try {
    await api('/api/admin/open-destination', { method: 'POST' });
    toast('LiDrop-Ordner wurde geöffnet.');
  } catch (error) { toast(error.message, true); }
}

async function removeDevice(id) {
  if (!confirm('Dieses Gerät entfernen?')) return;
  try {
    await api(`/api/admin/device/${id}`, { method: 'DELETE' });
    toast('Gerät entfernt.');
    await refreshAdmin(false);
  } catch (error) { toast(error.message, true); }
}

async function bulkDeleteDevices(scope) {
  if (!confirm('Offline-Geräte entfernen?')) return;
  try {
    const result = await api(`/api/admin/devices?scope=${encodeURIComponent(scope)}`, { method: 'DELETE' });
    toast(`${result.deleted || 0} Gerät(e) entfernt.`);
    await refreshAdmin(false);
  } catch (error) { toast(error.message, true); }
}

async function deleteTransfer(id) {
  try {
    await api(`/api/admin/transfer/${id}`, { method: 'DELETE' });
    await refreshAdmin(false);
  } catch (error) { toast(error.message, true); }
}

async function bulkDeleteTransfers(scope) {
  if (!confirm('Fertige Übertragungen aus der Liste entfernen? Die empfangenen Dateien bleiben im LiDrop-Ordner.')) return;
  try {
    const result = await api(`/api/admin/transfers?scope=${encodeURIComponent(scope)}`, { method: 'DELETE' });
    toast(`${result.deleted || 0} Einträge entfernt.`);
    await refreshAdmin(false);
  } catch (error) { toast(error.message, true); }
}

async function setTarget(id, deviceId) {
  if (!deviceId) return;
  try {
    await api(`/api/admin/outbound/${id}/target`, { method: 'POST', json: { deviceId } });
    toast('Gerät ausgewählt.');
    await refreshAdmin(false);
  } catch (error) { toast(error.message, true); }
}


function pairView() {
  app.innerHTML = `<div class="pair-screen">${topbar('Gerät verbinden')}<section class="panel pair-panel"><div class="brand-mark">⇅</div><h1>Mit LiDrop verbinden</h1><form id="pairForm"><label>Name<input id="deviceName" type="text" value="${esc(localStorage.getItem('limadDropDeviceName') || 'Mein Smartphone')}" maxlength="80" required></label><label>Code<input id="pairCodeInput" type="text" inputmode="numeric" pattern="[0-9 ]{6,7}" placeholder="000 000" ${pairFromUrl ? '' : 'required'}></label><button type="submit" class="primary">Verbinden</button></form><p class="fine">Gleiches WLAN. Empfangene Dateien werden automatisch gespeichert.</p></section></div>`;
  $('#pairForm').onsubmit = pairDevice;
}

async function pairDevice(event) {
  event.preventDefault();
  const button = $('button[type=submit]', event.currentTarget);
  const name = $('#deviceName').value.trim();
  const code = $('#pairCodeInput').value;
  button.disabled = true;
  button.textContent = 'Wird verbunden …';
  try {
    const data = await api('/api/pair', { method: 'POST', json: { name, code, token: pairFromUrl } });
    deviceToken = data.deviceToken;
    localStorage.setItem('limadDropDeviceToken', deviceToken);
    localStorage.setItem('limadDropDeviceName', data.name);
    history.replaceState(null, '', location.pathname);
    toast('Gerät wurde gekoppelt.');
    mobileView();
  } catch (error) {
    button.disabled = false;
    button.textContent = 'Gerät verbinden';
    toast(error.message, true);
  }
}

async function mobileView() {
  app.innerHTML = `<div class="mobile-main">${topbar(localStorage.getItem('limadDropDeviceName') || 'Verbunden')}<main class="mobile-clean"><section class="panel mobile-share"><div class="mobile-status"><span class="dot"></span><span>Mit LiDrop verbunden</span></div><div id="dropzone" class="dropzone clean-drop mobile-drop"><div class="drop-icon">⇧</div><strong>Dateien senden</strong><span>Auswählen oder hier ablegen</span><button id="pick" class="primary">Dateien auswählen</button><input id="files" class="hidden" type="file" multiple></div>${progressMarkup()}</section><section class="panel"><div class="section-title"><h2>Vom LiMaD-PC</h2></div><div id="downloads" class="list clean-list"></div></section><section class="panel"><div class="section-title"><h2>Zuletzt</h2></div><div id="mobileHistory" class="list clean-list"></div></section><button id="forget" class="ghost forget-button">Verbindung entfernen</button></main></div>`;
  bindMobile();
  await refreshMobile();
  refreshTimer = setInterval(refreshMobile, 900);
}

function bindMobile() {
  const input = $('#files');
  const drop = $('#dropzone');
  $('#pick').onclick = () => { if (!activeTransferController) input.click(); };
  input.onchange = () => mobileSend([...input.files]);
  ['dragenter', 'dragover'].forEach((name) => drop.addEventListener(name, (event) => { event.preventDefault(); if (!activeTransferController) drop.classList.add('drag'); }));
  ['dragleave', 'drop'].forEach((name) => drop.addEventListener(name, (event) => { event.preventDefault(); drop.classList.remove('drag'); }));
  drop.addEventListener('drop', (event) => { if (!activeTransferController) mobileSend([...event.dataTransfer.files]); });
  $('#forget').onclick = () => {
    if (confirm('Lokale Kopplung löschen? Das Gerät muss anschließend erneut gekoppelt werden.')) {
      localStorage.removeItem('limadDropDeviceToken');
      deviceToken = '';
      clearInterval(refreshTimer);
      pairView();
    }
  };
}

async function mobileSend(files) {
  await runUploadQueue(files, 'inbound', '', refreshMobile);
}

function prepareNativeDownload(transfer, link) {
  link.classList.add('busy');
  link.textContent = 'Download wird geöffnet …';
  toast(`${transfer.filename} wird an den Browser übergeben.`);
  setTimeout(() => refreshMobile(), 1200);
  setTimeout(() => {
    if (document.body.contains(link)) {
      link.classList.remove('busy');
      link.textContent = 'Auf Handy speichern';
    }
  }, 5000);
}

async function refreshMobile() {
  try {
    const current = await api('/api/mobile/state');
    const ready = current.outbound.filter((transfer) => transfer.status === 'ready');
    $('#downloads').innerHTML = ready.length ? ready.map((transfer) => `<div class="item"><div><div class="item-title">${esc(transfer.filename)}</div><div class="item-meta">${fmt(transfer.size)}</div></div><div class="item-actions"><a class="download-action" data-download="${esc(transfer.id)}" href="${esc(transfer.downloadUrl)}" download="${esc(transfer.filename)}">Auf Handy speichern</a></div></div>`).join('') : '<div class="empty">Der LiMaD-PC hat keine Datei bereitgestellt.</div>';
    $$('[data-download]').forEach((link) => {
      const transfer = ready.find((item) => item.id === link.dataset.download);
      link.onclick = () => prepareNativeDownload(transfer, link);
    });
    const historyItems = [...current.inbound, ...current.outbound].sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at))).slice(0, 8);
    $('#mobileHistory').innerHTML = historyItems.length ? historyItems.map((transfer) => `<div class="transfer-row clean-transfer"><div class="file-icon">${transfer.direction === 'inbound' ? '↑' : '↓'}</div><div class="transfer-copy"><div class="item-title">${esc(transfer.filename)}</div><div class="item-meta">${fmt(transfer.size)}</div>${transferProgress(transfer)}</div><span class="status-text ${['accepted','downloaded'].includes(transfer.status) ? 'good' : ''}">${statusLabel(transfer.status)}</span></div>`).join('') : '<div class="empty clean-empty">Noch keine Übertragung.</div>';
  } catch (error) {
    if (String(error.message).includes('gekoppelt')) {
      clearInterval(refreshTimer);
      localStorage.removeItem('limadDropDeviceToken');
      deviceToken = '';
      pairView();
    }
  }
}

(async () => {
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
  if (adminToken) return adminView();
  if (deviceToken) return mobileView();
  pairView();
})().catch((error) => {
  app.innerHTML = `<div class="pair-screen"><section class="panel"><h1>LiDrop konnte nicht geladen werden</h1><p>${esc(error.message)}</p></section></div>`;
});
