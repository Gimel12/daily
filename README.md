# Windows Remote Network Monitor

Monitor your home network remotely from your Mac. See what every device is visiting online by capturing DNS queries on a Windows PC connected to the same network. Auto-flags adult content, VPNs, dating apps, gambling, and more. Control the Windows PC and run commands from anywhere via Tailscale.

## Features

- **Two DNS capture modes** — works with or without router access
- **Auto-alerts** — flags adult content, VPN/proxy bypass, dating, gambling, drugs
- **Remote command execution** — run PowerShell/CMD commands from your Mac
- **Network scanning** — discover all devices on the home network
- **DNS query logging** — every domain lookup stored permanently with timestamps
- **Search & filter** — search by keyword ("tiktok", "youtube") or device IP
- **Historical reports** — generate browsing reports per device over any time period
- **Activity timeline** — see hourly activity breakdown per device
- **Domain categorization** — each domain auto-tagged (social media, gaming, streaming, etc.)
- **Live monitoring** — real-time tail of DNS queries with color-coded flags
- **Secure** — token-based auth over Tailscale (WireGuard encrypted)

---

## Quick Start (5 minutes)

### What You Need

| Machine | Requirements |
|---------|-------------|
| **Windows PC** (at home, on the network) | Python 3.10+, Npcap, Tailscale |
| **Your Mac** (anywhere) | Python 3.10+, Tailscale |

---

## Step-by-Step Deployment to Windows PC

### Step 1: Install Prerequisites on Windows

Open a browser on the Windows PC and install these three things:

**A) Python 3.10+**
1. Go to https://www.python.org/downloads/
2. Download and run the installer
3. **IMPORTANT**: Check "Add Python to PATH" at the bottom of the installer
4. Click "Install Now"

**B) Npcap (network packet capture driver)**
1. Go to https://npcap.com
2. Download and run the installer
3. Check **"WinPcap API-compatible mode"** during install
4. Click Install

**C) Tailscale**
1. Go to https://tailscale.com/download
2. Download and install the Windows version
3. Sign in with the same account as your Mac

### Step 2: Copy the Agent to Windows

Transfer the `windows_agent/` folder to the Windows PC. Options:
- **USB drive**: Copy to `C:\windows_agent\`
- **Tailscale file sharing**: `tailscale file cp windows_agent/ <windows-hostname>:`
- **Cloud drive**: Upload to Google Drive/OneDrive, download on Windows
- **Email**: Zip and email to yourself

### Step 3: Install Python Dependencies

On the Windows PC, open **Command Prompt as Administrator**:
1. Press `Win` key, type `cmd`
2. Right-click "Command Prompt" → **Run as administrator**
3. Run:
```
cd C:\windows_agent
install.bat
```

### Step 4: Configure the Agent

Open `C:\windows_agent\config.py` in Notepad and edit:

```python
# Set a strong secret token — you'll use this same token on your Mac
AUTH_TOKEN = "pick-any-strong-password-here-123"

# Your Xfinity router settings (already configured):
CAPTURE_MODE = "proxy"         # Use "proxy" with router access, "arp" without
GATEWAY_IP = "10.0.0.1"       # Xfinity default
NETWORK_CIDR = "10.0.0.0/24"  # Xfinity default subnet

# Your network adapter — run 'ipconfig' to find yours
INTERFACE = "Wi-Fi"            # Usually "Wi-Fi" or "Ethernet"
```

**To find your interface name**: Open Command Prompt and run `ipconfig`. Look for the adapter that has a `10.0.0.x` IP address. Use that adapter name.

### Step 5: Configure Xfinity Router (Mode A — Recommended)

Since you have router access at `http://10.0.0.1`:

1. First, find your Windows PC's local IP:
   ```
   ipconfig
   ```
   Look for `IPv4 Address` under your Wi-Fi/Ethernet adapter (e.g., `10.0.0.50`)

2. Open browser → go to `http://10.0.0.1`
3. Login: username `admin`, password `password`
4. Navigate to: **Gateway → Connection → Local IP Network**
5. Scroll to **DHCP** section
6. Set **DNS Server 1** to your Windows PC's IP (e.g., `10.0.0.50`)
7. Set **DNS Server 2** to `8.8.8.8`
8. Click **Save**

Now all devices on your network will send DNS queries through your Windows PC.

> **If Xfinity locks the DNS settings**: Change `config.py` to `CAPTURE_MODE = "arp"` — this works without any router changes.

### Step 6: Start the Agent

Right-click `C:\windows_agent\start.bat` → **Run as administrator**

You should see:
```
╔══════════════════════════════════════════════╗
║   Windows Remote Network Monitor v1.0        ║
║   Mode: PROXY                                ║
║   API:  http://0.0.0.0:8745                  ║
╚══════════════════════════════════════════════╝
```

### Step 7: Make It Run Automatically on Boot

So the agent starts every time the PC turns on:

1. Press `Win + R`, type `taskschd.msc`, press Enter
2. Click **Create Task** (right panel)
3. **General tab**:
   - Name: `Network Monitor`
   - Check **"Run with highest privileges"**
   - Configure for: Windows 10/11
4. **Triggers tab** → New:
   - Begin the task: **At startup**
5. **Actions tab** → New:
   - Action: Start a program
   - Program: `C:\windows_agent\start.bat`
   - Start in: `C:\windows_agent`
6. Click OK

The agent will now auto-start silently whenever the PC boots.

### Step 8: Setup Your Mac

On your Mac terminal:
```bash
cd mac_client
pip3 install -r requirements.txt
```

Edit `mac_client/remote.py` — set these two values at the top:
```python
AGENT_URL = "http://100.x.x.x:8745"    # Your Windows PC's Tailscale IP
AUTH_TOKEN = "pick-any-strong-password-here-123"  # Same token as config.py
```

**Find the Tailscale IP**: Run `tailscale status` on either machine. Look for your Windows PC's `100.x.x.x` address.

### Step 9: Test It

```bash
python3 remote.py status
```

If you see the status panel, everything is working.

---

## Usage

### Check agent status
```bash
python3 remote.py status
```

### Scan the network for devices
```bash
python3 remote.py scan
```

### List known devices
```bash
python3 remote.py devices
```

### Check alerts (flagged domains)
```bash
python3 remote.py alerts                          # All devices, last 24h
python3 remote.py alerts --hours 168              # Last 7 days
python3 remote.py alerts device 10.0.0.42         # Specific device
```

### View recent DNS queries
```bash
python3 remote.py dns list
python3 remote.py dns list --limit 50
```

### Search DNS queries by keyword
```bash
python3 remote.py dns search "tiktok"
python3 remote.py dns search "youtube" --from 2026-01-01 --to 2026-02-01
```

### View all unique domains with categories
```bash
python3 remote.py dns domains                     # All devices
python3 remote.py dns domains --ip 10.0.0.42      # Specific device
python3 remote.py dns domains --days 30           # Last 30 days
```

### View queries from a specific device
```bash
python3 remote.py dns device 10.0.0.42
python3 remote.py dns device 10.0.0.42 --from 2026-02-01
```

### Activity timeline (hourly breakdown)
```bash
python3 remote.py dns timeline 10.0.0.42          # When are they active?
python3 remote.py dns timeline 10.0.0.42 --days 30
```

### Generate a full browsing report for a device
```bash
python3 remote.py dns report 10.0.0.42 --days 30
```

### Live monitoring (real-time, color-coded)
```bash
python3 remote.py dns live
```
Flagged domains show in **RED** (adult/gambling) or **YELLOW** (VPN/dating).

### Execute commands on the Windows PC
```bash
python3 remote.py exec "ipconfig /all"
python3 remote.py exec "Get-Process" --shell powershell
python3 remote.py exec "netstat -an" --shell cmd
```

---

## Alert Categories

The system auto-flags these domain categories:

| Severity | Category | Examples |
|----------|----------|----------|
| **HIGH** | Adult Content | pornhub.com, onlyfans.com, xvideos.com |
| **HIGH** | Gambling | draftkings.com, bet365.com, stake.com |
| **HIGH** | Drugs | leafly.com, weedmaps.com |
| **HIGH** | Weapons | gunbroker.com |
| **HIGH** | Self-Harm | crisis resources (for awareness) |
| **MEDIUM** | Dating / Hookup | tinder.com, bumble.com, omegle.com |
| **MEDIUM** | VPN / Proxy Bypass | nordvpn.com, torproject.org, protonvpn.com |
| LOW | Social Media | tiktok.com, instagram.com, snapchat.com |
| LOW | Gaming | roblox.com, fortnite.com, discord.com |
| LOW | Streaming | youtube.com, netflix.com, twitch.tv |

You can add custom domains/keywords in `windows_agent/domain_categories.py`.

---

## DNS Capture Modes

| Feature | Mode A: DNS Proxy | Mode B: ARP Spoof |
|---------|-------------------|-------------------|
| Router access needed | Yes | No |
| Reliability | Very high | High |
| Setup difficulty | Easy (one router setting) | None (automatic) |
| Network impact | None | Minimal |
| Config value | `CAPTURE_MODE = "proxy"` | `CAPTURE_MODE = "arp"` |

**Your setup**: Since you have Xfinity router access at `10.0.0.1`, use **Mode A** (proxy). If the router locks DNS settings, switch to `CAPTURE_MODE = "arp"` as fallback.

---

## What You Can and Cannot See

| Visible (DNS monitoring) | Not visible (encrypted) |
|--------------------------|------------------------|
| Every domain/website visited | Actual search terms typed into Google |
| When they visit and how often | Specific pages within a site |
| Which device visits what | Content of messages/DMs |
| VPN/proxy bypass attempts | Activity inside apps |
| Adult/gambling/dating site visits | Incognito browsing content (domains still visible) |

**Important**: DNS monitoring shows domains even in incognito/private browsing mode. The only way to bypass it is if someone uses a VPN or DNS-over-HTTPS — which the agent flags as a **MEDIUM alert** (VPN/Proxy bypass category).

---

## Troubleshooting

**"Cannot connect to agent"**
- Ensure the agent is running on Windows (check `start.bat` output)
- Verify Tailscale is connected on both machines (`tailscale status`)
- Check the Tailscale IP is correct in `remote.py`

**"Npcap not detected"**
- Reinstall Npcap with "WinPcap API-compatible mode" checked

**"Permission denied" / ARP spoof not working**
- The agent MUST run as Administrator
- Right-click `start.bat` → "Run as administrator"

**No DNS queries captured**
- Mode A: Verify router DNS points to the Windows PC's IP (`ipconfig /all` on any device should show your PC's IP as DNS)
- Mode B: Run `python3 remote.py scan` to verify the agent can see devices
- Check that `INTERFACE` in `config.py` matches your network adapter name (run `ipconfig`)

**Agent crashes on startup**
- Check `agent.log` in the windows_agent folder for error details
- Verify `GATEWAY_IP` is correct (should be `10.0.0.1` for Xfinity)

**Xfinity won't let me change DNS**
- Some Xfinity gateways lock DNS settings
- Switch to `CAPTURE_MODE = "arp"` in `config.py` — works without any router changes
- Or try the Xfinity xFi app which sometimes has more options

---

## Security Notes

- All traffic between Mac and Windows goes through Tailscale (WireGuard encrypted)
- The API requires a token in every request — without it, requests are rejected
- The auth token is never transmitted in plain text over the internet (Tailscale encrypts it)
- The agent only listens on the Tailscale interface and local network
- Destructive commands (format, delete) are blocked by the safety filter
