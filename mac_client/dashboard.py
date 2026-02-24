#!/usr/bin/env python3
"""
Windows Remote Network Monitor — Web Dashboard
Run this on your Mac to get a visual web interface for monitoring.
"""
import requests
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from typing import Optional
import os

# ── Configuration (same as remote.py) ──────────────────────
AGENT_URL = "http://100.83.241.97:8745"
AUTH_TOKEN = "yeNTj8zguBu593SThEMvwIJ-_r9YLFuliNWT3JTzJA8"
DASHBOARD_PORT = 5555

app = FastAPI(title="Network Monitor Dashboard")


def _agent_get(path: str, params: dict = None) -> dict:
    """Proxy GET request to the Windows agent."""
    try:
        r = requests.get(
            f"{AGENT_URL}{path}",
            headers={"X-Auth-Token": AUTH_TOKEN},
            params=params,
            timeout=120,
        )
        r.raise_for_status()
        return r.json()
    except requests.ConnectionError:
        return {"error": "Cannot connect to Windows agent. Check Tailscale."}
    except Exception as e:
        return {"error": str(e)}


def _agent_post(path: str, data: dict = None) -> dict:
    """Proxy POST request to the Windows agent."""
    try:
        r = requests.post(
            f"{AGENT_URL}{path}",
            headers={"X-Auth-Token": AUTH_TOKEN},
            json=data,
            timeout=120,
        )
        r.raise_for_status()
        return r.json()
    except requests.ConnectionError:
        return {"error": "Cannot connect to Windows agent. Check Tailscale."}
    except Exception as e:
        return {"error": str(e)}


# ── API proxy endpoints ─────────────────────────────────────

@app.get("/api/status")
async def api_status():
    return JSONResponse(_agent_get("/status"))

@app.get("/api/scan")
async def api_scan():
    return JSONResponse(_agent_get("/scan"))

@app.get("/api/devices")
async def api_devices():
    return JSONResponse(_agent_get("/devices"))

@app.get("/api/alerts")
async def api_alerts(hours: int = 24):
    return JSONResponse(_agent_get("/alerts", {"hours": hours}))

@app.get("/api/alerts/device/{ip}")
async def api_alerts_device(ip: str, hours: int = 24):
    return JSONResponse(_agent_get(f"/alerts/device/{ip}", {"hours": hours}))

@app.get("/api/dns/list")
async def api_dns_list(limit: int = 100, offset: int = 0):
    return JSONResponse(_agent_get("/dns/list", {"limit": limit, "offset": offset}))

@app.get("/api/dns/search")
async def api_dns_search(term: str, limit: int = 200):
    return JSONResponse(_agent_get("/dns/search", {"term": term, "limit": limit}))

@app.get("/api/dns/device/{ip}")
async def api_dns_device(ip: str, limit: int = 200):
    return JSONResponse(_agent_get(f"/dns/device/{ip}", {"limit": limit}))

@app.get("/api/dns/domains")
async def api_dns_domains(ip: Optional[str] = None, days: int = 7, limit: int = 200):
    params = {"days": days, "limit": limit}
    if ip:
        params["ip"] = ip
    return JSONResponse(_agent_get("/dns/domains", params))

@app.get("/api/dns/report/{ip}")
async def api_dns_report(ip: str, days: int = 30):
    return JSONResponse(_agent_get(f"/dns/report/{ip}", {"days": days}))

@app.get("/api/dns/timeline/{ip}")
async def api_dns_timeline(ip: str, days: int = 7):
    return JSONResponse(_agent_get(f"/dns/timeline/{ip}", {"days": days}))

@app.post("/api/exec")
async def api_exec(request: Request):
    data = await request.json()
    return JSONResponse(_agent_post("/exec", data))


# ── Dashboard HTML ──────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Network Monitor</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>tailwind.config={darkMode:'class',theme:{extend:{colors:{bg:'#0f172a',card:'#1e293b',accent:'#3b82f6',danger:'#ef4444',warning:'#f59e0b',success:'#22c55e'}}}}</script>
<style>
  body { background: #0f172a; color: #e2e8f0; font-family: 'Inter', system-ui, sans-serif; }
  .glow { box-shadow: 0 0 20px rgba(59,130,246,0.15); }
  .pulse { animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.6} }
  .fade-in { animation: fadeIn 0.3s ease-in; }
  @keyframes fadeIn { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: #1e293b; }
  ::-webkit-scrollbar-thumb { background: #475569; border-radius: 3px; }
  .severity-high { color: #ef4444; font-weight: 700; }
  .severity-medium { color: #f59e0b; font-weight: 600; }
  .severity-low { color: #94a3b8; }
  .tab-active { border-bottom: 2px solid #3b82f6; color: #3b82f6; }
  .tab { cursor: pointer; padding: 0.75rem 1.25rem; transition: all 0.2s; }
  .tab:hover { color: #93c5fd; }
  #live-dot { width:8px;height:8px;border-radius:50%;display:inline-block; }
  .live-on { background:#22c55e; box-shadow:0 0 6px #22c55e; }
  .live-off { background:#64748b; }
</style>
</head>
<body class="min-h-screen">

<!-- Header -->
<header class="bg-card border-b border-slate-700 px-6 py-4 flex items-center justify-between">
  <div class="flex items-center gap-3">
    <div class="w-10 h-10 bg-accent rounded-lg flex items-center justify-center text-white font-bold text-lg">N</div>
    <div>
      <h1 class="text-xl font-bold text-white">Network Monitor</h1>
      <p class="text-xs text-slate-400" id="status-line">Connecting...</p>
    </div>
  </div>
  <div class="flex items-center gap-4">
    <span id="live-dot" class="live-off"></span>
    <button onclick="toggleLive()" id="live-btn" class="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded text-sm transition">Start Live</button>
    <button onclick="refreshAll()" class="px-3 py-1.5 bg-accent hover:bg-blue-600 rounded text-sm text-white transition">Refresh</button>
  </div>
</header>

<!-- Tabs -->
<nav class="bg-card border-b border-slate-700 flex px-6" id="tabs">
  <div class="tab tab-active" data-tab="overview" onclick="switchTab('overview')">Overview</div>
  <div class="tab" data-tab="alerts" onclick="switchTab('alerts')">Alerts</div>
  <div class="tab" data-tab="devices" onclick="switchTab('devices')">Devices</div>
  <div class="tab" data-tab="dns" onclick="switchTab('dns')">DNS Queries</div>
  <div class="tab" data-tab="search" onclick="switchTab('search')">Search</div>
  <div class="tab" data-tab="terminal" onclick="switchTab('terminal')">Terminal</div>
</nav>

<!-- Content -->
<main class="p-6 max-w-7xl mx-auto">

  <!-- Overview Tab -->
  <div id="tab-overview" class="tab-content fade-in">
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      <div class="bg-card rounded-xl p-5 glow">
        <p class="text-slate-400 text-sm">Total Queries</p>
        <p class="text-3xl font-bold text-white mt-1" id="stat-total">-</p>
      </div>
      <div class="bg-card rounded-xl p-5 glow">
        <p class="text-slate-400 text-sm">Queries Today</p>
        <p class="text-3xl font-bold text-white mt-1" id="stat-today">-</p>
      </div>
      <div class="bg-card rounded-xl p-5 glow">
        <p class="text-slate-400 text-sm">Unique Devices</p>
        <p class="text-3xl font-bold text-accent mt-1" id="stat-devices">-</p>
      </div>
      <div class="bg-card rounded-xl p-5 glow">
        <p class="text-slate-400 text-sm">Active Alerts</p>
        <p class="text-3xl font-bold mt-1" id="stat-alerts">-</p>
      </div>
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="bg-card rounded-xl p-5 glow">
        <h3 class="text-lg font-semibold mb-3 text-white">Agent Status</h3>
        <div id="agent-info" class="text-sm space-y-2 text-slate-300"></div>
      </div>
      <div class="bg-card rounded-xl p-5 glow">
        <h3 class="text-lg font-semibold mb-3 text-white">Recent Alerts</h3>
        <div id="recent-alerts" class="text-sm space-y-2"></div>
      </div>
    </div>
  </div>

  <!-- Alerts Tab -->
  <div id="tab-alerts" class="tab-content hidden fade-in">
    <div class="flex items-center gap-4 mb-4">
      <h2 class="text-xl font-bold">Alerts</h2>
      <select id="alert-hours" onchange="loadAlerts()" class="bg-slate-700 rounded px-3 py-1.5 text-sm">
        <option value="24">Last 24 hours</option>
        <option value="72">Last 3 days</option>
        <option value="168">Last 7 days</option>
        <option value="720">Last 30 days</option>
      </select>
      <select id="alert-device" onchange="loadAlerts()" class="bg-slate-700 rounded px-3 py-1.5 text-sm">
        <option value="">All devices</option>
      </select>
    </div>
    <div id="alerts-list" class="bg-card rounded-xl overflow-hidden"></div>
  </div>

  <!-- Devices Tab -->
  <div id="tab-devices" class="tab-content hidden fade-in">
    <div class="flex items-center gap-4 mb-4">
      <h2 class="text-xl font-bold">Network Devices</h2>
      <button onclick="scanNetwork()" class="px-3 py-1.5 bg-accent hover:bg-blue-600 rounded text-sm text-white transition">Scan Network</button>
    </div>
    <div id="devices-list" class="bg-card rounded-xl overflow-hidden"></div>
  </div>

  <!-- DNS Tab -->
  <div id="tab-dns" class="tab-content hidden fade-in">
    <div class="flex items-center gap-4 mb-4">
      <h2 class="text-xl font-bold">DNS Queries</h2>
      <select id="dns-device-filter" onchange="loadDNS()" class="bg-slate-700 rounded px-3 py-1.5 text-sm">
        <option value="">All devices</option>
      </select>
      <select id="dns-limit" onchange="loadDNS()" class="bg-slate-700 rounded px-3 py-1.5 text-sm">
        <option value="50">50</option>
        <option value="100" selected>100</option>
        <option value="200">200</option>
        <option value="500">500</option>
      </select>
    </div>
    <div id="dns-list" class="bg-card rounded-xl overflow-hidden"></div>
  </div>

  <!-- Search Tab -->
  <div id="tab-search" class="tab-content hidden fade-in">
    <div class="flex items-center gap-4 mb-4">
      <h2 class="text-xl font-bold">Search DNS</h2>
      <input type="text" id="search-input" placeholder="Search domains (e.g. tiktok, youtube)..." class="bg-slate-700 rounded px-4 py-2 text-sm flex-1 max-w-md focus:outline-none focus:ring-2 focus:ring-accent" onkeydown="if(event.key==='Enter')doSearch()">
      <button onclick="doSearch()" class="px-4 py-2 bg-accent hover:bg-blue-600 rounded text-sm text-white transition">Search</button>
    </div>
    <div id="search-results" class="bg-card rounded-xl overflow-hidden"></div>
  </div>

  <!-- Terminal Tab -->
  <div id="tab-terminal" class="tab-content hidden fade-in">
    <div class="flex items-center gap-4 mb-4">
      <h2 class="text-xl font-bold">Remote Terminal</h2>
      <select id="term-shell" class="bg-slate-700 rounded px-3 py-1.5 text-sm">
        <option value="powershell">PowerShell</option>
        <option value="cmd">CMD</option>
      </select>
    </div>
    <div class="flex gap-2 mb-4">
      <input type="text" id="term-input" placeholder="Enter command..." class="bg-slate-700 rounded px-4 py-2 text-sm flex-1 font-mono focus:outline-none focus:ring-2 focus:ring-accent" onkeydown="if(event.key==='Enter')runCommand()">
      <button onclick="runCommand()" class="px-4 py-2 bg-accent hover:bg-blue-600 rounded text-sm text-white transition">Run</button>
    </div>
    <div id="term-output" class="bg-slate-900 rounded-xl p-4 font-mono text-sm min-h-[300px] max-h-[500px] overflow-auto whitespace-pre-wrap"></div>
  </div>

  <!-- Live Feed (overlay at bottom) -->
  <div id="live-feed" class="hidden mt-6 bg-card rounded-xl p-4 glow">
    <div class="flex items-center justify-between mb-3">
      <h3 class="font-semibold text-white flex items-center gap-2">
        <span id="live-dot2" class="live-on" style="width:8px;height:8px;border-radius:50%;display:inline-block"></span>
        Live DNS Feed
      </h3>
      <button onclick="toggleLive()" class="text-sm text-slate-400 hover:text-white">Stop</button>
    </div>
    <div id="live-entries" class="space-y-1 max-h-[300px] overflow-auto font-mono text-xs"></div>
  </div>

</main>

<script>
// ── State ──────────────────────────────────────────────────
let liveInterval = null;
let liveLastId = 0;
let knownDevices = [];

// ── Tab switching ──────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('tab-active'));
  document.getElementById('tab-' + name).classList.remove('hidden');
  document.querySelector(`.tab[data-tab="${name}"]`).classList.add('tab-active');

  if (name === 'alerts') loadAlerts();
  if (name === 'devices') loadDevices();
  if (name === 'dns') loadDNS();
}

// ── API helpers ────────────────────────────────────────────
async function api(path) {
  try {
    const r = await fetch('/api' + path);
    return await r.json();
  } catch(e) {
    return { error: e.message };
  }
}
async function apiPost(path, body) {
  try {
    const r = await fetch('/api' + path, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
    return await r.json();
  } catch(e) {
    return { error: e.message };
  }
}

// ── Overview ───────────────────────────────────────────────
async function loadOverview() {
  const data = await api('/status');
  if (data.error) {
    document.getElementById('status-line').textContent = 'Disconnected';
    document.getElementById('status-line').className = 'text-xs text-red-400';
    return;
  }

  document.getElementById('status-line').textContent =
    `Connected | Mode: ${data.capture_mode.toUpperCase()} | ${data.local_ip}`;
  document.getElementById('status-line').className = 'text-xs text-green-400';

  document.getElementById('stat-total').textContent = (data.dns_stats?.total_queries ?? 0).toLocaleString();
  document.getElementById('stat-today').textContent = (data.dns_stats?.queries_today ?? 0).toLocaleString();
  document.getElementById('stat-devices').textContent = data.dns_stats?.unique_devices ?? 0;

  const info = document.getElementById('agent-info');
  info.innerHTML = `
    <div class="flex justify-between"><span class="text-slate-400">Mode</span><span>${data.capture_mode.toUpperCase()}</span></div>
    <div class="flex justify-between"><span class="text-slate-400">Local IP</span><span>${data.local_ip}</span></div>
    <div class="flex justify-between"><span class="text-slate-400">Gateway</span><span>${data.gateway_ip}</span></div>
    <div class="flex justify-between"><span class="text-slate-400">Network</span><span>${data.network}</span></div>
    <div class="flex justify-between"><span class="text-slate-400">Interface</span><span>${data.interface}</span></div>
    <hr class="border-slate-600 my-2">
    <div class="flex justify-between"><span class="text-slate-400">DNS Proxy</span><span class="${data.components.dns_proxy?'text-green-400':'text-slate-500'}">${data.components.dns_proxy?'ON':'OFF'}</span></div>
    <div class="flex justify-between"><span class="text-slate-400">ARP Spoofer</span><span class="${data.components.arp_spoofer?'text-green-400':'text-slate-500'}">${data.components.arp_spoofer?'ON':'OFF'}</span></div>
    <div class="flex justify-between"><span class="text-slate-400">DNS Sniffer</span><span class="${data.components.dns_sniffer?'text-green-400':'text-slate-500'}">${data.components.dns_sniffer?'ON':'OFF'}</span></div>
  `;

  // Load alerts count
  const alerts = await api('/alerts?hours=24');
  if (!alerts.error) {
    const count = alerts.count || 0;
    const el = document.getElementById('stat-alerts');
    el.textContent = count;
    el.className = count > 0 ? 'text-3xl font-bold mt-1 text-danger' : 'text-3xl font-bold mt-1 text-success';

    // Recent alerts
    const recentDiv = document.getElementById('recent-alerts');
    if (alerts.alerts && alerts.alerts.length > 0) {
      recentDiv.innerHTML = alerts.alerts.slice(0, 8).map(a => {
        const sevClass = a.severity === 'high' ? 'severity-high' : 'severity-medium';
        const ts = (a.timestamp || '').replace('T',' ').slice(0,19);
        return `<div class="flex items-center justify-between py-1.5 border-b border-slate-700">
          <div>
            <span class="${sevClass} text-xs uppercase mr-2">${a.severity}</span>
            <span class="text-slate-400 text-xs">${a.label}</span>
          </div>
          <div>
            <span class="text-cyan-400">${a.domain}</span>
            <span class="text-slate-500 text-xs ml-2">${a.source_ip}</span>
          </div>
        </div>`;
      }).join('');
    } else {
      recentDiv.innerHTML = '<p class="text-green-400 text-sm">No alerts in the last 24 hours</p>';
    }
  }
}

// ── Alerts ─────────────────────────────────────────────────
async function loadAlerts() {
  const hours = document.getElementById('alert-hours').value;
  const device = document.getElementById('alert-device').value;
  const path = device ? `/alerts/device/${device}?hours=${hours}` : `/alerts?hours=${hours}`;
  const data = await api(path);

  if (data.error) { document.getElementById('alerts-list').innerHTML = `<p class="p-4 text-red-400">${data.error}</p>`; return; }

  if (!data.alerts || data.alerts.length === 0) {
    document.getElementById('alerts-list').innerHTML = '<p class="p-6 text-green-400 text-center">No alerts found</p>';
    return;
  }

  let html = `<table class="w-full text-sm">
    <thead><tr class="bg-slate-800 text-slate-400 text-xs uppercase">
      <th class="px-4 py-3 text-left">Severity</th>
      <th class="px-4 py-3 text-left">Category</th>
      <th class="px-4 py-3 text-left">Domain</th>
      <th class="px-4 py-3 text-left">Device</th>
      <th class="px-4 py-3 text-left">Time</th>
    </tr></thead><tbody>`;

  data.alerts.forEach(a => {
    const sevClass = a.severity === 'high' ? 'severity-high' : 'severity-medium';
    const ts = (a.timestamp || '').replace('T',' ').slice(0,19);
    html += `<tr class="border-b border-slate-700 hover:bg-slate-800/50">
      <td class="px-4 py-2.5 ${sevClass} uppercase text-xs">${a.severity}</td>
      <td class="px-4 py-2.5 text-slate-300">${a.label}</td>
      <td class="px-4 py-2.5 text-cyan-400">${a.domain}</td>
      <td class="px-4 py-2.5"><a href="#" onclick="viewDevice('${a.source_ip}')" class="text-accent hover:underline">${a.source_ip}</a></td>
      <td class="px-4 py-2.5 text-slate-500">${ts}</td>
    </tr>`;
  });
  html += '</tbody></table>';
  document.getElementById('alerts-list').innerHTML = html;
}

// ── Devices ────────────────────────────────────────────────
async function loadDevices() {
  const data = await api('/devices');
  if (data.error) { document.getElementById('devices-list').innerHTML = `<p class="p-4 text-red-400">${data.error}</p>`; return; }

  knownDevices = data.devices || [];
  populateDeviceDropdowns();

  if (knownDevices.length === 0) {
    document.getElementById('devices-list').innerHTML = '<p class="p-6 text-slate-400 text-center">No devices found. Click Scan Network.</p>';
    return;
  }

  let html = `<table class="w-full text-sm">
    <thead><tr class="bg-slate-800 text-slate-400 text-xs uppercase">
      <th class="px-4 py-3 text-left">IP</th>
      <th class="px-4 py-3 text-left">MAC</th>
      <th class="px-4 py-3 text-left">Hostname</th>
      <th class="px-4 py-3 text-left">Vendor</th>
      <th class="px-4 py-3 text-left">Last Seen</th>
      <th class="px-4 py-3 text-left">Actions</th>
    </tr></thead><tbody>`;

  knownDevices.forEach(d => {
    const ls = (d.last_seen || '').replace('T',' ').slice(0,19);
    html += `<tr class="border-b border-slate-700 hover:bg-slate-800/50">
      <td class="px-4 py-2.5 font-semibold text-white">${d.ip}</td>
      <td class="px-4 py-2.5 font-mono text-xs text-slate-400">${d.mac}</td>
      <td class="px-4 py-2.5">${d.hostname || '-'}</td>
      <td class="px-4 py-2.5 text-slate-400">${d.vendor || '-'}</td>
      <td class="px-4 py-2.5 text-slate-500">${ls}</td>
      <td class="px-4 py-2.5">
        <button onclick="viewDevice('${d.ip}')" class="text-accent hover:underline text-xs mr-2">DNS</button>
        <button onclick="viewAlerts('${d.ip}')" class="text-warning hover:underline text-xs mr-2">Alerts</button>
        <button onclick="viewReport('${d.ip}')" class="text-green-400 hover:underline text-xs">Report</button>
      </td>
    </tr>`;
  });
  html += '</tbody></table>';
  document.getElementById('devices-list').innerHTML = html;
}

async function scanNetwork() {
  document.getElementById('devices-list').innerHTML = '<p class="p-6 text-cyan-400 text-center pulse">Scanning network...</p>';
  const data = await api('/scan');
  loadDevices();
}

function populateDeviceDropdowns() {
  const selects = ['alert-device', 'dns-device-filter'];
  selects.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    const current = el.value;
    el.innerHTML = '<option value="">All devices</option>';
    knownDevices.forEach(d => {
      const label = d.hostname ? `${d.ip} (${d.hostname})` : d.ip;
      el.innerHTML += `<option value="${d.ip}">${label}</option>`;
    });
    el.value = current;
  });
}

// ── DNS Queries ────────────────────────────────────────────
async function loadDNS() {
  const device = document.getElementById('dns-device-filter').value;
  const limit = document.getElementById('dns-limit').value;
  const path = device ? `/dns/device/${device}?limit=${limit}` : `/dns/list?limit=${limit}`;
  const data = await api(path);

  if (data.error) { document.getElementById('dns-list').innerHTML = `<p class="p-4 text-red-400">${data.error}</p>`; return; }

  const queries = data.queries || [];
  if (queries.length === 0) {
    document.getElementById('dns-list').innerHTML = '<p class="p-6 text-slate-400 text-center">No DNS queries recorded yet</p>';
    return;
  }

  let html = `<table class="w-full text-sm">
    <thead><tr class="bg-slate-800 text-slate-400 text-xs uppercase">
      <th class="px-4 py-3 text-left">Time</th>
      <th class="px-4 py-3 text-left">Device</th>
      <th class="px-4 py-3 text-left">Domain</th>
      <th class="px-4 py-3 text-left">Type</th>
    </tr></thead><tbody>`;

  queries.forEach(q => {
    const ts = (q.timestamp || '').replace('T',' ').slice(0,19);
    html += `<tr class="border-b border-slate-700 hover:bg-slate-800/50">
      <td class="px-4 py-2 text-slate-500 text-xs">${ts}</td>
      <td class="px-4 py-2"><a href="#" onclick="viewDevice('${q.source_ip}')" class="text-accent hover:underline">${q.source_ip}</a></td>
      <td class="px-4 py-2 text-cyan-400">${q.domain}</td>
      <td class="px-4 py-2 text-slate-500 text-xs">${q.query_type || 'A'}</td>
    </tr>`;
  });
  html += '</tbody></table>';
  document.getElementById('dns-list').innerHTML = html;
}

// ── Search ─────────────────────────────────────────────────
async function doSearch() {
  const term = document.getElementById('search-input').value.trim();
  if (!term) return;

  document.getElementById('search-results').innerHTML = '<p class="p-6 text-cyan-400 text-center pulse">Searching...</p>';
  const data = await api(`/dns/search?term=${encodeURIComponent(term)}&limit=200`);

  if (data.error) { document.getElementById('search-results').innerHTML = `<p class="p-4 text-red-400">${data.error}</p>`; return; }

  const queries = data.queries || [];
  if (queries.length === 0) {
    document.getElementById('search-results').innerHTML = `<p class="p-6 text-slate-400 text-center">No results for "${term}"</p>`;
    return;
  }

  let html = `<div class="px-4 py-2 bg-slate-800 text-sm text-slate-400">${data.count} results for "${term}"</div>`;
  html += `<table class="w-full text-sm"><thead><tr class="bg-slate-800/50 text-slate-400 text-xs uppercase">
    <th class="px-4 py-2 text-left">Time</th>
    <th class="px-4 py-2 text-left">Device</th>
    <th class="px-4 py-2 text-left">Domain</th>
    <th class="px-4 py-2 text-left">Type</th>
  </tr></thead><tbody>`;

  queries.forEach(q => {
    const ts = (q.timestamp || '').replace('T',' ').slice(0,19);
    const highlighted = q.domain.replace(new RegExp(`(${term})`,'gi'), '<span class="bg-yellow-500/30 text-yellow-300">$1</span>');
    html += `<tr class="border-b border-slate-700 hover:bg-slate-800/50">
      <td class="px-4 py-2 text-slate-500 text-xs">${ts}</td>
      <td class="px-4 py-2"><a href="#" onclick="viewDevice('${q.source_ip}')" class="text-accent hover:underline">${q.source_ip}</a></td>
      <td class="px-4 py-2 text-cyan-400">${highlighted}</td>
      <td class="px-4 py-2 text-slate-500 text-xs">${q.query_type || 'A'}</td>
    </tr>`;
  });
  html += '</tbody></table>';
  document.getElementById('search-results').innerHTML = html;
}

// ── Terminal ───────────────────────────────────────────────
async function runCommand() {
  const cmd = document.getElementById('term-input').value.trim();
  if (!cmd) return;

  const shell = document.getElementById('term-shell').value;
  const out = document.getElementById('term-output');
  out.innerHTML += `<span class="text-green-400">$ ${cmd}</span>\\n<span class="text-slate-500">Running...</span>\\n`;
  out.scrollTop = out.scrollHeight;

  const data = await apiPost('/exec', { command: cmd, shell, timeout: 60 });
  // Remove "Running..."
  out.innerHTML = out.innerHTML.replace('<span class="text-slate-500">Running...</span>\\n', '');

  if (data.stdout) out.innerHTML += `<span class="text-slate-200">${escHtml(data.stdout)}</span>`;
  if (data.stderr) out.innerHTML += `<span class="text-red-400">${escHtml(data.stderr)}</span>`;
  out.innerHTML += '\\n';
  out.scrollTop = out.scrollHeight;
  document.getElementById('term-input').value = '';
}

function escHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// ── Live Feed ──────────────────────────────────────────────
function toggleLive() {
  if (liveInterval) {
    clearInterval(liveInterval);
    liveInterval = null;
    document.getElementById('live-feed').classList.add('hidden');
    document.getElementById('live-dot').className = 'live-off';
    document.getElementById('live-btn').textContent = 'Start Live';
  } else {
    document.getElementById('live-feed').classList.remove('hidden');
    document.getElementById('live-dot').className = 'live-on';
    document.getElementById('live-btn').textContent = 'Stop Live';
    liveInterval = setInterval(pollLive, 2000);
    pollLive();
  }
}

const HIGH_KW = ['porn','xxx','nsfw','hentai','onlyfans','fap','nude','casino','gambling','betting'];
const HIGH_DOM = ['pornhub.com','xvideos.com','xnxx.com','xhamster.com','onlyfans.com','chaturbate.com','draftkings.com','bet365.com'];
const MED_KW = ['vpn','unblock','proxy-','hookup','dating'];
const MED_DOM = ['tinder.com','bumble.com','omegle.com','nordvpn.com','expressvpn.com','torproject.org'];

function liveSeverity(d) {
  d = d.toLowerCase();
  for (const k of HIGH_KW) if (d.includes(k)) return 'high';
  for (const dd of HIGH_DOM) if (d===dd || d.endsWith('.'+dd)) return 'high';
  for (const k of MED_KW) if (d.includes(k)) return 'medium';
  for (const dd of MED_DOM) if (d===dd || d.endsWith('.'+dd)) return 'medium';
  return null;
}

async function pollLive() {
  const data = await api('/dns/list?limit=20');
  if (data.error || !data.queries) return;

  const container = document.getElementById('live-entries');
  data.queries.reverse().forEach(q => {
    if (q.id <= liveLastId) return;
    liveLastId = q.id;

    const ts = (q.timestamp||'').replace('T',' ').slice(11,19);
    const sev = liveSeverity(q.domain);
    let cls = 'text-cyan-400';
    let flag = '';
    if (sev === 'high') { cls = 'text-red-400 font-bold'; flag = ' *** FLAGGED ***'; }
    else if (sev === 'medium') { cls = 'text-yellow-400'; flag = ' * flagged *'; }

    const entry = document.createElement('div');
    entry.innerHTML = `<span class="text-slate-500">${ts}</span> <span class="text-white">${q.source_ip}</span> <span class="${cls}">${q.domain}${flag}</span>`;
    container.appendChild(entry);

    // Keep max 200 entries
    while (container.children.length > 200) container.removeChild(container.firstChild);
  });
  container.scrollTop = container.scrollHeight;
}

// ── Helpers ────────────────────────────────────────────────
function viewDevice(ip) {
  document.getElementById('dns-device-filter').value = ip;
  switchTab('dns');
  loadDNS();
}
function viewAlerts(ip) {
  document.getElementById('alert-device').value = ip;
  switchTab('alerts');
  loadAlerts();
}
async function viewReport(ip) {
  switchTab('dns');
  document.getElementById('dns-list').innerHTML = '<p class="p-6 text-cyan-400 text-center pulse">Loading report...</p>';
  const data = await api(`/dns/report/${ip}?days=30`);
  if (data.error) { document.getElementById('dns-list').innerHTML = `<p class="p-4 text-red-400">${data.error}</p>`; return; }

  let html = `<div class="p-5">
    <h3 class="text-lg font-bold text-white mb-2">30-Day Report for ${ip}</h3>
    <p class="text-slate-400 mb-4">Total queries: <span class="text-white font-bold">${(data.total_queries||0).toLocaleString()}</span></p>`;

  if (data.top_domains && data.top_domains.length) {
    html += `<h4 class="font-semibold text-white mt-4 mb-2">Top Domains</h4><table class="w-full text-sm mb-4">
      <thead><tr class="text-slate-400 text-xs uppercase"><th class="text-left py-1">#</th><th class="text-left py-1">Domain</th><th class="text-left py-1">Hits</th></tr></thead><tbody>`;
    data.top_domains.slice(0,30).forEach((d,i) => {
      html += `<tr class="border-b border-slate-700"><td class="py-1.5 text-slate-500">${i+1}</td><td class="py-1.5 text-cyan-400">${d.domain}</td><td class="py-1.5 font-semibold">${d.cnt}</td></tr>`;
    });
    html += '</tbody></table>';
  }

  if (data.daily_breakdown && data.daily_breakdown.length) {
    const maxDay = Math.max(...data.daily_breakdown.map(d=>d.cnt));
    html += `<h4 class="font-semibold text-white mt-4 mb-2">Daily Activity</h4><div class="space-y-1">`;
    data.daily_breakdown.forEach(d => {
      const pct = maxDay > 0 ? (d.cnt/maxDay*100) : 0;
      html += `<div class="flex items-center gap-2 text-xs">
        <span class="w-20 text-slate-400">${d.day}</span>
        <div class="flex-1 bg-slate-700 rounded h-4"><div class="bg-accent rounded h-4" style="width:${pct}%"></div></div>
        <span class="w-12 text-right">${d.cnt}</span>
      </div>`;
    });
    html += '</div>';
  }
  html += '</div>';
  document.getElementById('dns-list').innerHTML = html;
}

async function refreshAll() {
  await loadOverview();
  const devData = await api('/devices');
  if (!devData.error) { knownDevices = devData.devices || []; populateDeviceDropdowns(); }
}

// ── Init ───────────────────────────────────────────────────
loadOverview();
api('/devices').then(d => { if (!d.error) { knownDevices = d.devices || []; populateDeviceDropdowns(); }});
</script>
</body>
</html>"""


if __name__ == "__main__":
    print(f"""
    ╔══════════════════════════════════════════════╗
    ║   Network Monitor Dashboard                  ║
    ║   Open: http://localhost:{DASHBOARD_PORT}               ║
    ╚══════════════════════════════════════════════╝
    """)
    uvicorn.run("dashboard:app", host="127.0.0.1", port=DASHBOARD_PORT, log_level="warning")
