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
<script>tailwind.config={darkMode:'class',theme:{extend:{colors:{bg:'#0f172a',card:'#1e293b',card2:'#253349',accent:'#3b82f6',danger:'#ef4444',warning:'#f59e0b',success:'#22c55e'}}}}</script>
<style>
  body{background:#0f172a;color:#e2e8f0;font-family:'Inter',system-ui,sans-serif}
  .glow{box-shadow:0 0 20px rgba(59,130,246,0.15)}
  .glow-red{box-shadow:0 0 15px rgba(239,68,68,0.2)}
  .pulse{animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.6}}
  .fade-in{animation:fadeIn .3s ease-in}
  @keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
  ::-webkit-scrollbar{width:6px}
  ::-webkit-scrollbar-track{background:#1e293b}
  ::-webkit-scrollbar-thumb{background:#475569;border-radius:3px}
  .severity-high{color:#ef4444;font-weight:700}
  .severity-medium{color:#f59e0b;font-weight:600}
  .severity-low{color:#94a3b8}
  .tab-active{border-bottom:2px solid #3b82f6;color:#3b82f6}
  .tab{cursor:pointer;padding:.75rem 1.25rem;transition:all .2s}
  .tab:hover{color:#93c5fd}
  .dot{width:8px;height:8px;border-radius:50%;display:inline-block}
  .live-on{background:#22c55e;box-shadow:0 0 6px #22c55e}
  .live-off{background:#64748b}
  .dev-card{transition:all .2s;cursor:pointer}
  .dev-card:hover{transform:translateY(-2px);box-shadow:0 4px 20px rgba(59,130,246,0.2)}
  .section-tab{cursor:pointer;padding:.5rem 1rem;border-radius:.5rem;transition:all .2s;font-size:.875rem}
  .section-tab:hover{background:#334155}
  .section-tab-active{background:#3b82f6;color:white}
</style>
</head>
<body class="min-h-screen">

<header class="bg-card border-b border-slate-700 px-6 py-4 flex items-center justify-between">
  <div class="flex items-center gap-3">
    <div class="w-10 h-10 bg-accent rounded-lg flex items-center justify-center text-white font-bold text-lg">N</div>
    <div>
      <h1 class="text-xl font-bold text-white">Network Monitor</h1>
      <p class="text-xs text-slate-400" id="status-line">Connecting...</p>
    </div>
  </div>
  <div class="flex items-center gap-4">
    <span class="dot live-off" id="live-dot"></span>
    <button onclick="toggleLive()" id="live-btn" class="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded text-sm transition">Start Live</button>
    <button onclick="refreshAll()" class="px-3 py-1.5 bg-accent hover:bg-blue-600 rounded text-sm text-white transition">Refresh</button>
  </div>
</header>

<nav class="bg-card border-b border-slate-700 flex px-6" id="tabs">
  <div class="tab tab-active" data-tab="overview" onclick="switchTab('overview')">Overview</div>
  <div class="tab" data-tab="alerts" onclick="switchTab('alerts')">Alerts</div>
  <div class="tab" data-tab="devices" onclick="switchTab('devices')">Devices</div>
  <div class="tab" data-tab="device" onclick="switchTab('device')" id="tab-device-nav" style="display:none">
    <span id="tab-device-label">Device</span>
  </div>
  <div class="tab" data-tab="dns" onclick="switchTab('dns')">DNS Queries</div>
  <div class="tab" data-tab="search" onclick="switchTab('search')">Search</div>
  <div class="tab" data-tab="terminal" onclick="switchTab('terminal')">Terminal</div>
</nav>

<main class="p-6 max-w-7xl mx-auto">

  <!-- OVERVIEW -->
  <div id="tab-overview" class="tab-content fade-in">
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      <div class="bg-card rounded-xl p-5 glow"><p class="text-slate-400 text-sm">Total Queries</p><p class="text-3xl font-bold text-white mt-1" id="stat-total">-</p></div>
      <div class="bg-card rounded-xl p-5 glow"><p class="text-slate-400 text-sm">Queries Today</p><p class="text-3xl font-bold text-white mt-1" id="stat-today">-</p></div>
      <div class="bg-card rounded-xl p-5 glow"><p class="text-slate-400 text-sm">Unique Devices</p><p class="text-3xl font-bold text-accent mt-1" id="stat-devices">-</p></div>
      <div class="bg-card rounded-xl p-5 glow"><p class="text-slate-400 text-sm">Active Alerts</p><p class="text-3xl font-bold mt-1" id="stat-alerts">-</p></div>
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

  <!-- ALERTS -->
  <div id="tab-alerts" class="tab-content hidden fade-in">
    <div class="flex items-center gap-4 mb-4">
      <h2 class="text-xl font-bold">Alerts</h2>
      <select id="alert-hours" onchange="loadAlerts()" class="bg-slate-700 rounded px-3 py-1.5 text-sm">
        <option value="24">Last 24 hours</option><option value="72">Last 3 days</option><option value="168">Last 7 days</option><option value="720">Last 30 days</option>
      </select>
      <select id="alert-device" onchange="loadAlerts()" class="bg-slate-700 rounded px-3 py-1.5 text-sm"><option value="">All devices</option></select>
    </div>
    <div id="alerts-list" class="bg-card rounded-xl overflow-hidden"></div>
  </div>

  <!-- DEVICES LIST -->
  <div id="tab-devices" class="tab-content hidden fade-in">
    <div class="flex items-center gap-4 mb-4">
      <h2 class="text-xl font-bold">Network Devices</h2>
      <button onclick="scanNetwork()" class="px-3 py-1.5 bg-accent hover:bg-blue-600 rounded text-sm text-white transition">Scan Network</button>
    </div>
    <p class="text-slate-400 text-sm mb-4">Click on any device to see its full browsing activity</p>
    <div id="devices-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"></div>
  </div>

  <!-- DEVICE DETAIL -->
  <div id="tab-device" class="tab-content hidden fade-in">
    <div class="flex items-center gap-3 mb-4">
      <button onclick="switchTab('devices')" class="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded text-sm transition">&larr; Back</button>
      <h2 class="text-xl font-bold" id="dev-title">Device</h2>
    </div>
    <!-- Device info bar -->
    <div class="bg-card rounded-xl p-4 mb-4 flex flex-wrap items-center gap-6 glow" id="dev-info-bar"></div>
    <!-- Device stats -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4" id="dev-stats"></div>
    <!-- Section tabs -->
    <div class="flex gap-2 mb-4 flex-wrap" id="dev-sections">
      <div class="section-tab section-tab-active" onclick="devSection('domains')">Top Domains</div>
      <div class="section-tab" onclick="devSection('queries')">Recent Queries</div>
      <div class="section-tab" onclick="devSection('timeline')">Timeline</div>
      <div class="section-tab" onclick="devSection('devalerts')">Alerts</div>
      <div class="section-tab" onclick="devSection('devlive')">Live Feed</div>
    </div>
    <div id="dev-content" class="bg-card rounded-xl overflow-hidden"></div>
  </div>

  <!-- DNS QUERIES -->
  <div id="tab-dns" class="tab-content hidden fade-in">
    <div class="flex items-center gap-4 mb-4">
      <h2 class="text-xl font-bold">DNS Queries</h2>
      <select id="dns-device-filter" onchange="loadDNS()" class="bg-slate-700 rounded px-3 py-1.5 text-sm"><option value="">All devices</option></select>
      <select id="dns-limit" onchange="loadDNS()" class="bg-slate-700 rounded px-3 py-1.5 text-sm">
        <option value="50">50</option><option value="100" selected>100</option><option value="200">200</option><option value="500">500</option>
      </select>
    </div>
    <div id="dns-list" class="bg-card rounded-xl overflow-hidden"></div>
  </div>

  <!-- SEARCH -->
  <div id="tab-search" class="tab-content hidden fade-in">
    <div class="flex items-center gap-4 mb-4">
      <h2 class="text-xl font-bold">Search DNS</h2>
      <input type="text" id="search-input" placeholder="Search domains (e.g. tiktok, youtube)..." class="bg-slate-700 rounded px-4 py-2 text-sm flex-1 max-w-md focus:outline-none focus:ring-2 focus:ring-accent" onkeydown="if(event.key==='Enter')doSearch()">
      <button onclick="doSearch()" class="px-4 py-2 bg-accent hover:bg-blue-600 rounded text-sm text-white transition">Search</button>
    </div>
    <div id="search-results" class="bg-card rounded-xl overflow-hidden"></div>
  </div>

  <!-- TERMINAL -->
  <div id="tab-terminal" class="tab-content hidden fade-in">
    <div class="flex items-center gap-4 mb-4">
      <h2 class="text-xl font-bold">Remote Terminal</h2>
      <select id="term-shell" class="bg-slate-700 rounded px-3 py-1.5 text-sm"><option value="powershell">PowerShell</option><option value="cmd">CMD</option></select>
    </div>
    <div class="flex gap-2 mb-4">
      <input type="text" id="term-input" placeholder="Enter command..." class="bg-slate-700 rounded px-4 py-2 text-sm flex-1 font-mono focus:outline-none focus:ring-2 focus:ring-accent" onkeydown="if(event.key==='Enter')runCommand()">
      <button onclick="runCommand()" class="px-4 py-2 bg-accent hover:bg-blue-600 rounded text-sm text-white transition">Run</button>
    </div>
    <div id="term-output" class="bg-slate-900 rounded-xl p-4 font-mono text-sm min-h-[300px] max-h-[500px] overflow-auto whitespace-pre-wrap"></div>
  </div>

  <!-- LIVE FEED -->
  <div id="live-feed" class="hidden mt-6 bg-card rounded-xl p-4 glow">
    <div class="flex items-center justify-between mb-3">
      <h3 class="font-semibold text-white flex items-center gap-2"><span class="dot live-on"></span> Live DNS Feed</h3>
      <button onclick="toggleLive()" class="text-sm text-slate-400 hover:text-white">Stop</button>
    </div>
    <div id="live-entries" class="space-y-1 max-h-[300px] overflow-auto font-mono text-xs"></div>
  </div>
</main>

<script>
let liveInterval=null, liveLastId=0, knownDevices=[], currentDeviceIp=null, devLiveInterval=null, devLiveLastId=0, currentDevSection='domains';

// ── Severity check ────────────────────────────────────────
const HIGH_KW=['porn','xxx','nsfw','hentai','onlyfans','fap','nude','casino','gambling','betting','sexo'];
const HIGH_DOM=['pornhub.com','xvideos.com','xnxx.com','xhamster.com','onlyfans.com','chaturbate.com','draftkings.com','bet365.com','stake.com','redtube.com'];
const MED_KW=['vpn','unblock','proxy-','hookup','dating'];
const MED_DOM=['tinder.com','bumble.com','omegle.com','nordvpn.com','expressvpn.com','torproject.org','protonvpn.com'];
function sev(d){d=d.toLowerCase();for(const k of HIGH_KW)if(d.includes(k))return'high';for(const x of HIGH_DOM)if(d===x||d.endsWith('.'+x))return'high';for(const k of MED_KW)if(d.includes(k))return'medium';for(const x of MED_DOM)if(d===x||d.endsWith('.'+x))return'medium';return null}
function sevBadge(s){if(s==='high')return'<span class="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-xs font-bold">HIGH</span>';if(s==='medium')return'<span class="px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-400 text-xs font-semibold">MEDIUM</span>';return''}
function escHtml(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}

// ── Tab switching ─────────────────────────────────────────
function switchTab(name){
  document.querySelectorAll('.tab-content').forEach(el=>el.classList.add('hidden'));
  document.querySelectorAll('.tab').forEach(el=>el.classList.remove('tab-active'));
  document.getElementById('tab-'+name).classList.remove('hidden');
  const navTab=document.querySelector(`.tab[data-tab="${name}"]`);
  if(navTab)navTab.classList.add('tab-active');
  if(name==='alerts')loadAlerts();
  if(name==='devices')loadDevices();
  if(name==='dns')loadDNS();
  // Stop device live feed if leaving device tab
  if(name!=='device'&&devLiveInterval){clearInterval(devLiveInterval);devLiveInterval=null}
}

// ── API helpers ───────────────────────────────────────────
async function api(p){try{const r=await fetch('/api'+p);return await r.json()}catch(e){return{error:e.message}}}
async function apiPost(p,b){try{const r=await fetch('/api'+p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});return await r.json()}catch(e){return{error:e.message}}}

// ── Overview ──────────────────────────────────────────────
async function loadOverview(){
  const data=await api('/status');
  if(data.error){document.getElementById('status-line').textContent='Disconnected';document.getElementById('status-line').className='text-xs text-red-400';return}
  document.getElementById('status-line').textContent=`Connected | Mode: ${data.capture_mode.toUpperCase()} | ${data.local_ip}`;
  document.getElementById('status-line').className='text-xs text-green-400';
  document.getElementById('stat-total').textContent=(data.dns_stats?.total_queries??0).toLocaleString();
  document.getElementById('stat-today').textContent=(data.dns_stats?.queries_today??0).toLocaleString();
  document.getElementById('stat-devices').textContent=data.dns_stats?.unique_devices??0;
  document.getElementById('agent-info').innerHTML=`
    <div class="flex justify-between"><span class="text-slate-400">Mode</span><span>${data.capture_mode.toUpperCase()}</span></div>
    <div class="flex justify-between"><span class="text-slate-400">Local IP</span><span>${data.local_ip}</span></div>
    <div class="flex justify-between"><span class="text-slate-400">Gateway</span><span>${data.gateway_ip}</span></div>
    <div class="flex justify-between"><span class="text-slate-400">Network</span><span>${data.network}</span></div>
    <div class="flex justify-between"><span class="text-slate-400">Interface</span><span>${data.interface}</span></div>
    <hr class="border-slate-600 my-2">
    <div class="flex justify-between"><span class="text-slate-400">DNS Proxy</span><span class="${data.components.dns_proxy?'text-green-400':'text-slate-500'}">${data.components.dns_proxy?'ON':'OFF'}</span></div>
    <div class="flex justify-between"><span class="text-slate-400">ARP Spoofer</span><span class="${data.components.arp_spoofer?'text-green-400':'text-slate-500'}">${data.components.arp_spoofer?'ON':'OFF'}</span></div>
    <div class="flex justify-between"><span class="text-slate-400">DNS Sniffer</span><span class="${data.components.dns_sniffer?'text-green-400':'text-slate-500'}">${data.components.dns_sniffer?'ON':'OFF'}</span></div>`;
  const alerts=await api('/alerts?hours=24');
  if(!alerts.error){
    const c=alerts.count||0;
    const el=document.getElementById('stat-alerts');el.textContent=c;
    el.className=c>0?'text-3xl font-bold mt-1 text-danger':'text-3xl font-bold mt-1 text-success';
    const rd=document.getElementById('recent-alerts');
    if(alerts.alerts&&alerts.alerts.length>0){
      rd.innerHTML=alerts.alerts.slice(0,8).map(a=>{
        const sc=a.severity==='high'?'severity-high':'severity-medium';
        return`<div class="flex items-center justify-between py-1.5 border-b border-slate-700 cursor-pointer hover:bg-slate-800/50" onclick="openDevice('${a.source_ip}')">
          <div><span class="${sc} text-xs uppercase mr-2">${a.severity}</span><span class="text-slate-400 text-xs">${a.label}</span></div>
          <div><span class="text-cyan-400">${a.domain}</span><span class="text-slate-500 text-xs ml-2">${a.source_ip}</span></div></div>`}).join('');
    }else{rd.innerHTML='<p class="text-green-400 text-sm">No alerts in the last 24 hours</p>'}
  }
}

// ── Alerts ────────────────────────────────────────────────
async function loadAlerts(){
  const h=document.getElementById('alert-hours').value,dv=document.getElementById('alert-device').value;
  const p=dv?`/alerts/device/${dv}?hours=${h}`:`/alerts?hours=${h}`;
  const data=await api(p);
  if(data.error){document.getElementById('alerts-list').innerHTML=`<p class="p-4 text-red-400">${data.error}</p>`;return}
  if(!data.alerts||!data.alerts.length){document.getElementById('alerts-list').innerHTML='<p class="p-6 text-green-400 text-center">No alerts found</p>';return}
  let html=`<table class="w-full text-sm"><thead><tr class="bg-slate-800 text-slate-400 text-xs uppercase">
    <th class="px-4 py-3 text-left">Severity</th><th class="px-4 py-3 text-left">Category</th><th class="px-4 py-3 text-left">Domain</th><th class="px-4 py-3 text-left">Device</th><th class="px-4 py-3 text-left">Time</th></tr></thead><tbody>`;
  data.alerts.forEach(a=>{const sc=a.severity==='high'?'severity-high':'severity-medium';const ts=(a.timestamp||'').replace('T',' ').slice(0,19);
    html+=`<tr class="border-b border-slate-700 hover:bg-slate-800/50 cursor-pointer" onclick="openDevice('${a.source_ip}')">
      <td class="px-4 py-2.5 ${sc} uppercase text-xs">${a.severity}</td><td class="px-4 py-2.5 text-slate-300">${a.label}</td>
      <td class="px-4 py-2.5 text-cyan-400">${a.domain}</td><td class="px-4 py-2.5 text-accent">${a.source_ip}</td><td class="px-4 py-2.5 text-slate-500">${ts}</td></tr>`});
  html+='</tbody></table>';document.getElementById('alerts-list').innerHTML=html;
}

// ── Devices Grid ──────────────────────────────────────────
async function loadDevices(){
  const data=await api('/devices');
  if(data.error){document.getElementById('devices-grid').innerHTML=`<p class="text-red-400">${data.error}</p>`;return}
  knownDevices=data.devices||[];populateDeviceDropdowns();
  if(!knownDevices.length){document.getElementById('devices-grid').innerHTML='<p class="col-span-3 text-slate-400 text-center py-8">No devices found. Click Scan Network.</p>';return}
  // Also fetch scan data for online status
  let html='';
  knownDevices.forEach(d=>{
    const ls=(d.last_seen||'').replace('T',' ').slice(0,19);
    const name=d.hostname?d.hostname.split('.')[0]:d.ip;
    html+=`<div class="bg-card rounded-xl p-5 dev-card glow" onclick="openDevice('${d.ip}')">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2">
          <div class="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center text-accent text-sm font-bold">${d.ip.split('.').pop()}</div>
          <div><p class="font-semibold text-white text-sm">${name}</p><p class="text-xs text-slate-500">${d.ip}</p></div>
        </div>
      </div>
      <div class="text-xs text-slate-400 space-y-1">
        <div class="flex justify-between"><span>MAC</span><span class="font-mono">${d.mac}</span></div>
        <div class="flex justify-between"><span>Vendor</span><span>${d.vendor||'-'}</span></div>
        <div class="flex justify-between"><span>Last seen</span><span>${ls}</span></div>
      </div>
      <div class="mt-3 pt-3 border-t border-slate-700 text-center">
        <span class="text-accent text-xs font-semibold">Click to view activity &rarr;</span>
      </div>
    </div>`});
  document.getElementById('devices-grid').innerHTML=html;
}

async function scanNetwork(){
  document.getElementById('devices-grid').innerHTML='<p class="col-span-3 text-cyan-400 text-center py-8 pulse">Scanning network...</p>';
  await api('/scan');loadDevices();
}

function populateDeviceDropdowns(){
  ['alert-device','dns-device-filter'].forEach(id=>{
    const el=document.getElementById(id);if(!el)return;const cur=el.value;
    el.innerHTML='<option value="">All devices</option>';
    knownDevices.forEach(d=>{const l=d.hostname?`${d.ip} (${d.hostname.split('.')[0]})`:d.ip;el.innerHTML+=`<option value="${d.ip}">${l}</option>`});
    el.value=cur;
  });
}

// ── DEVICE DETAIL ─────────────────────────────────────────
async function openDevice(ip){
  currentDeviceIp=ip;
  // Show device tab in nav
  document.getElementById('tab-device-nav').style.display='';
  const devInfo=knownDevices.find(d=>d.ip===ip);
  const name=devInfo?.hostname?devInfo.hostname.split('.')[0]:ip;
  document.getElementById('tab-device-label').textContent=name;
  document.getElementById('dev-title').textContent=`${name} (${ip})`;
  switchTab('device');

  // Info bar
  const infoBar=document.getElementById('dev-info-bar');
  infoBar.innerHTML=`
    <div><span class="text-slate-400 text-xs block">IP Address</span><span class="font-semibold text-white">${ip}</span></div>
    <div><span class="text-slate-400 text-xs block">MAC</span><span class="font-mono text-sm">${devInfo?.mac||'-'}</span></div>
    <div><span class="text-slate-400 text-xs block">Hostname</span><span>${devInfo?.hostname||'-'}</span></div>
    <div><span class="text-slate-400 text-xs block">Vendor</span><span>${devInfo?.vendor||'-'}</span></div>
    <div><span class="text-slate-400 text-xs block">First Seen</span><span class="text-xs">${(devInfo?.first_seen||'').replace('T',' ').slice(0,19)}</span></div>
    <div><span class="text-slate-400 text-xs block">Last Seen</span><span class="text-xs">${(devInfo?.last_seen||'').replace('T',' ').slice(0,19)}</span></div>`;

  // Stats cards - load report + alerts concurrently
  const [report, alertsData] = await Promise.all([
    api(`/dns/report/${ip}?days=30`),
    api(`/alerts/device/${ip}?hours=720`)
  ]);
  const statsDiv=document.getElementById('dev-stats');
  const totalQ=report.total_queries||0;
  const alertCount=alertsData.count||0;
  const topDomain=report.top_domains?.length?report.top_domains[0].domain:'-';
  const daysActive=report.daily_breakdown?.length||0;
  statsDiv.innerHTML=`
    <div class="bg-card rounded-xl p-4 glow"><p class="text-slate-400 text-xs">Total Queries (30d)</p><p class="text-2xl font-bold text-white">${totalQ.toLocaleString()}</p></div>
    <div class="bg-card rounded-xl p-4 ${alertCount>0?'glow-red':'glow'}"><p class="text-slate-400 text-xs">Alerts (30d)</p><p class="text-2xl font-bold ${alertCount>0?'text-danger':'text-success'}">${alertCount}</p></div>
    <div class="bg-card rounded-xl p-4 glow"><p class="text-slate-400 text-xs">Top Domain</p><p class="text-sm font-bold text-cyan-400 mt-1 truncate">${topDomain}</p></div>
    <div class="bg-card rounded-xl p-4 glow"><p class="text-slate-400 text-xs">Active Days</p><p class="text-2xl font-bold text-white">${daysActive}</p></div>`;

  // Store data for sections
  window._devReport=report;
  window._devAlerts=alertsData;
  devSection('domains');
}

function devSection(name){
  currentDevSection=name;
  document.querySelectorAll('#dev-sections .section-tab').forEach(el=>el.classList.remove('section-tab-active'));
  const tabs=document.querySelectorAll('#dev-sections .section-tab');
  const names=['domains','queries','timeline','devalerts','devlive'];
  const idx=names.indexOf(name);
  if(idx>=0&&tabs[idx])tabs[idx].classList.add('section-tab-active');

  if(name==='domains')loadDevDomains();
  else if(name==='queries')loadDevQueries();
  else if(name==='timeline')loadDevTimeline();
  else if(name==='devalerts')loadDevAlerts();
  else if(name==='devlive')startDevLive();

  // Stop dev live if switching away
  if(name!=='devlive'&&devLiveInterval){clearInterval(devLiveInterval);devLiveInterval=null}
}

async function loadDevDomains(){
  const c=document.getElementById('dev-content');
  c.innerHTML='<p class="p-6 text-cyan-400 text-center pulse">Loading domains...</p>';
  const data=await api(`/dns/domains?ip=${currentDeviceIp}&days=30&limit=100`);
  if(data.error){c.innerHTML=`<p class="p-4 text-red-400">${data.error}</p>`;return}
  if(!data.domains?.length){c.innerHTML='<p class="p-6 text-slate-400 text-center">No domains recorded yet</p>';return}
  let html=`<table class="w-full text-sm"><thead><tr class="bg-slate-800 text-slate-400 text-xs uppercase">
    <th class="px-4 py-3 text-left">#</th><th class="px-4 py-3 text-left">Domain</th><th class="px-4 py-3 text-left">Visits</th>
    <th class="px-4 py-3 text-left">Category</th><th class="px-4 py-3 text-left">Severity</th><th class="px-4 py-3 text-left">Last Visit</th></tr></thead><tbody>`;
  data.domains.forEach((d,i)=>{
    const ls=(d.last_seen||'').replace('T',' ').slice(0,19);
    const catLabel=d.category_label||'';
    const severity=d.severity||'';
    const badge=sevBadge(severity);
    const catColor=severity==='high'?'text-red-400':severity==='medium'?'text-yellow-400':'text-slate-400';
    html+=`<tr class="border-b border-slate-700 hover:bg-slate-800/50">
      <td class="px-4 py-2 text-slate-500 text-xs">${i+1}</td>
      <td class="px-4 py-2 text-cyan-400 font-medium">${d.domain}</td>
      <td class="px-4 py-2 font-bold">${d.cnt}</td>
      <td class="px-4 py-2 ${catColor} text-xs">${catLabel}</td>
      <td class="px-4 py-2">${badge}</td>
      <td class="px-4 py-2 text-slate-500 text-xs">${ls}</td></tr>`});
  html+='</tbody></table>';c.innerHTML=html;
}

async function loadDevQueries(){
  const c=document.getElementById('dev-content');
  c.innerHTML='<p class="p-6 text-cyan-400 text-center pulse">Loading queries...</p>';
  const data=await api(`/dns/device/${currentDeviceIp}?limit=200`);
  if(data.error){c.innerHTML=`<p class="p-4 text-red-400">${data.error}</p>`;return}
  if(!data.queries?.length){c.innerHTML='<p class="p-6 text-slate-400 text-center">No queries yet</p>';return}
  let html=`<table class="w-full text-sm"><thead><tr class="bg-slate-800 text-slate-400 text-xs uppercase">
    <th class="px-4 py-3 text-left">Time</th><th class="px-4 py-3 text-left">Domain</th><th class="px-4 py-3 text-left">Type</th><th class="px-4 py-3 text-left">Flag</th></tr></thead><tbody>`;
  data.queries.forEach(q=>{
    const ts=(q.timestamp||'').replace('T',' ').slice(0,19);
    const s=sev(q.domain);const badge=s?sevBadge(s):'';
    const cls=s==='high'?'text-red-400 font-semibold':s==='medium'?'text-yellow-400':'text-cyan-400';
    html+=`<tr class="border-b border-slate-700 hover:bg-slate-800/50">
      <td class="px-4 py-2 text-slate-500 text-xs">${ts}</td><td class="px-4 py-2 ${cls}">${q.domain}</td>
      <td class="px-4 py-2 text-slate-500 text-xs">${q.query_type||'A'}</td><td class="px-4 py-2">${badge}</td></tr>`});
  html+='</tbody></table>';c.innerHTML=html;
}

async function loadDevTimeline(){
  const c=document.getElementById('dev-content');
  c.innerHTML='<p class="p-6 text-cyan-400 text-center pulse">Loading timeline...</p>';
  const data=await api(`/dns/timeline/${currentDeviceIp}?days=7`);
  if(data.error){c.innerHTML=`<p class="p-4 text-red-400">${data.error}</p>`;return}
  if(!data.timeline?.length){c.innerHTML='<p class="p-6 text-slate-400 text-center">No activity yet</p>';return}
  const maxC=Math.max(...data.timeline.map(t=>t.cnt));
  let html='<div class="p-5"><h3 class="font-semibold text-white mb-4">Hourly Activity (Last 7 Days)</h3><div class="space-y-1">';
  data.timeline.forEach(t=>{
    const pct=maxC>0?(t.cnt/maxC*100):0;
    const hour=t.hour.slice(11)||t.hour;
    const day=t.hour.slice(0,10);
    html+=`<div class="flex items-center gap-2 text-xs">
      <span class="w-28 text-slate-400 shrink-0">${day} ${hour}</span>
      <div class="flex-1 bg-slate-700 rounded h-5 relative"><div class="bg-accent rounded h-5 transition-all" style="width:${pct}%"></div></div>
      <span class="w-12 text-right font-semibold">${t.cnt}</span></div>`});
  html+='</div></div>';

  // Also show daily breakdown from report
  if(window._devReport?.daily_breakdown?.length){
    const dd=window._devReport.daily_breakdown;
    const maxD=Math.max(...dd.map(d=>d.cnt));
    html+='<div class="p-5 border-t border-slate-700"><h3 class="font-semibold text-white mb-4">Daily Breakdown (30 Days)</h3><div class="space-y-1">';
    dd.forEach(d=>{
      const pct=maxD>0?(d.cnt/maxD*100):0;
      html+=`<div class="flex items-center gap-2 text-xs">
        <span class="w-24 text-slate-400">${d.day}</span>
        <div class="flex-1 bg-slate-700 rounded h-4"><div class="bg-green-500 rounded h-4" style="width:${pct}%"></div></div>
        <span class="w-12 text-right">${d.cnt}</span></div>`});
    html+='</div></div>';
  }
  c.innerHTML=html;
}

async function loadDevAlerts(){
  const c=document.getElementById('dev-content');
  const data=window._devAlerts||await api(`/alerts/device/${currentDeviceIp}?hours=720`);
  if(!data.alerts?.length){c.innerHTML='<p class="p-6 text-green-400 text-center">No alerts for this device</p>';return}
  let html=`<table class="w-full text-sm"><thead><tr class="bg-slate-800 text-slate-400 text-xs uppercase">
    <th class="px-4 py-3 text-left">Severity</th><th class="px-4 py-3 text-left">Category</th><th class="px-4 py-3 text-left">Domain</th><th class="px-4 py-3 text-left">Time</th></tr></thead><tbody>`;
  data.alerts.forEach(a=>{const ts=(a.timestamp||'').replace('T',' ').slice(0,19);
    html+=`<tr class="border-b border-slate-700 hover:bg-slate-800/50">
      <td class="px-4 py-2.5">${sevBadge(a.severity)}</td><td class="px-4 py-2.5 text-slate-300">${a.label}</td>
      <td class="px-4 py-2.5 text-cyan-400">${a.domain}</td><td class="px-4 py-2.5 text-slate-500">${ts}</td></tr>`});
  html+='</tbody></table>';c.innerHTML=html;
}

function startDevLive(){
  const c=document.getElementById('dev-content');
  devLiveLastId=0;
  c.innerHTML=`<div class="p-4"><div class="flex items-center gap-2 mb-3"><span class="dot live-on"></span><span class="text-white font-semibold text-sm">Live feed for ${currentDeviceIp}</span></div>
    <div id="dev-live-entries" class="space-y-1 max-h-[400px] overflow-auto font-mono text-xs"></div></div>`;
  if(devLiveInterval)clearInterval(devLiveInterval);
  devLiveInterval=setInterval(pollDevLive,2000);
  pollDevLive();
}

async function pollDevLive(){
  const data=await api(`/dns/device/${currentDeviceIp}?limit=20`);
  if(data.error||!data.queries)return;
  const container=document.getElementById('dev-live-entries');
  if(!container)return;
  data.queries.reverse().forEach(q=>{
    if(q.id<=devLiveLastId)return;
    devLiveLastId=q.id;
    const ts=(q.timestamp||'').replace('T',' ').slice(11,19);
    const s=sev(q.domain);
    let cls='text-cyan-400',flag='';
    if(s==='high'){cls='text-red-400 font-bold';flag=' *** FLAGGED ***'}
    else if(s==='medium'){cls='text-yellow-400';flag=' * flagged *'}
    const entry=document.createElement('div');
    entry.innerHTML=`<span class="text-slate-500">${ts}</span> <span class="${cls}">${q.domain}${flag}</span>`;
    container.appendChild(entry);
    while(container.children.length>200)container.removeChild(container.firstChild);
  });
  container.scrollTop=container.scrollHeight;
}

// ── DNS Queries ───────────────────────────────────────────
async function loadDNS(){
  const dv=document.getElementById('dns-device-filter').value,lim=document.getElementById('dns-limit').value;
  const p=dv?`/dns/device/${dv}?limit=${lim}`:`/dns/list?limit=${lim}`;
  const data=await api(p);
  if(data.error){document.getElementById('dns-list').innerHTML=`<p class="p-4 text-red-400">${data.error}</p>`;return}
  const queries=data.queries||[];
  if(!queries.length){document.getElementById('dns-list').innerHTML='<p class="p-6 text-slate-400 text-center">No DNS queries recorded yet</p>';return}
  let html=`<table class="w-full text-sm"><thead><tr class="bg-slate-800 text-slate-400 text-xs uppercase">
    <th class="px-4 py-3 text-left">Time</th><th class="px-4 py-3 text-left">Device</th><th class="px-4 py-3 text-left">Domain</th><th class="px-4 py-3 text-left">Type</th></tr></thead><tbody>`;
  queries.forEach(q=>{const ts=(q.timestamp||'').replace('T',' ').slice(0,19);
    html+=`<tr class="border-b border-slate-700 hover:bg-slate-800/50 cursor-pointer" onclick="openDevice('${q.source_ip}')">
      <td class="px-4 py-2 text-slate-500 text-xs">${ts}</td><td class="px-4 py-2 text-accent">${q.source_ip}</td>
      <td class="px-4 py-2 text-cyan-400">${q.domain}</td><td class="px-4 py-2 text-slate-500 text-xs">${q.query_type||'A'}</td></tr>`});
  html+='</tbody></table>';document.getElementById('dns-list').innerHTML=html;
}

// ── Search ────────────────────────────────────────────────
async function doSearch(){
  const term=document.getElementById('search-input').value.trim();if(!term)return;
  document.getElementById('search-results').innerHTML='<p class="p-6 text-cyan-400 text-center pulse">Searching...</p>';
  const data=await api(`/dns/search?term=${encodeURIComponent(term)}&limit=200`);
  if(data.error){document.getElementById('search-results').innerHTML=`<p class="p-4 text-red-400">${data.error}</p>`;return}
  if(!data.queries?.length){document.getElementById('search-results').innerHTML=`<p class="p-6 text-slate-400 text-center">No results for "${term}"</p>`;return}
  let html=`<div class="px-4 py-2 bg-slate-800 text-sm text-slate-400">${data.count} results for "${term}"</div>
    <table class="w-full text-sm"><thead><tr class="bg-slate-800/50 text-slate-400 text-xs uppercase">
    <th class="px-4 py-2 text-left">Time</th><th class="px-4 py-2 text-left">Device</th><th class="px-4 py-2 text-left">Domain</th><th class="px-4 py-2 text-left">Type</th></tr></thead><tbody>`;
  data.queries.forEach(q=>{const ts=(q.timestamp||'').replace('T',' ').slice(0,19);
    const hl=q.domain.replace(new RegExp(`(${term.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&')})`,'gi'),'<span class="bg-yellow-500/30 text-yellow-300">$1</span>');
    html+=`<tr class="border-b border-slate-700 hover:bg-slate-800/50 cursor-pointer" onclick="openDevice('${q.source_ip}')">
      <td class="px-4 py-2 text-slate-500 text-xs">${ts}</td><td class="px-4 py-2 text-accent">${q.source_ip}</td>
      <td class="px-4 py-2 text-cyan-400">${hl}</td><td class="px-4 py-2 text-slate-500 text-xs">${q.query_type||'A'}</td></tr>`});
  html+='</tbody></table>';document.getElementById('search-results').innerHTML=html;
}

// ── Terminal ──────────────────────────────────────────────
async function runCommand(){
  const cmd=document.getElementById('term-input').value.trim();if(!cmd)return;
  const shell=document.getElementById('term-shell').value,out=document.getElementById('term-output');
  out.innerHTML+=`<span class="text-green-400">$ ${escHtml(cmd)}</span>\\n<span class="text-slate-500 pulse">Running...</span>\\n`;out.scrollTop=out.scrollHeight;
  const data=await apiPost('/exec',{command:cmd,shell,timeout:60});
  out.innerHTML=out.innerHTML.replace('<span class="text-slate-500 pulse">Running...</span>\\n','');
  if(data.stdout)out.innerHTML+=`<span class="text-slate-200">${escHtml(data.stdout)}</span>`;
  if(data.stderr)out.innerHTML+=`<span class="text-red-400">${escHtml(data.stderr)}</span>`;
  out.innerHTML+='\\n';out.scrollTop=out.scrollHeight;document.getElementById('term-input').value='';
}

// ── Global Live Feed ──────────────────────────────────────
function toggleLive(){
  if(liveInterval){clearInterval(liveInterval);liveInterval=null;
    document.getElementById('live-feed').classList.add('hidden');document.getElementById('live-dot').className='dot live-off';document.getElementById('live-btn').textContent='Start Live';
  }else{document.getElementById('live-feed').classList.remove('hidden');document.getElementById('live-dot').className='dot live-on';document.getElementById('live-btn').textContent='Stop Live';
    liveInterval=setInterval(pollLive,2000);pollLive()}
}
async function pollLive(){
  const data=await api('/dns/list?limit=20');if(data.error||!data.queries)return;
  const container=document.getElementById('live-entries');
  data.queries.reverse().forEach(q=>{
    if(q.id<=liveLastId)return;liveLastId=q.id;
    const ts=(q.timestamp||'').replace('T',' ').slice(11,19);const s=sev(q.domain);
    let cls='text-cyan-400',flag='';
    if(s==='high'){cls='text-red-400 font-bold';flag=' *** FLAGGED ***'}
    else if(s==='medium'){cls='text-yellow-400';flag=' * flagged *'}
    const entry=document.createElement('div');
    entry.innerHTML=`<span class="text-slate-500">${ts}</span> <span class="text-white">${q.source_ip}</span> <span class="${cls}">${q.domain}${flag}</span>`;
    container.appendChild(entry);
    while(container.children.length>200)container.removeChild(container.firstChild);
  });container.scrollTop=container.scrollHeight;
}

async function refreshAll(){await loadOverview();const d=await api('/devices');if(!d.error){knownDevices=d.devices||[];populateDeviceDropdowns()}}

// ── Init ──────────────────────────────────────────────────
loadOverview();
api('/devices').then(d=>{if(!d.error){knownDevices=d.devices||[];populateDeviceDropdowns()}});
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
