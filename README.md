
<p align="center">
<img src="assets\DB-Nav-Buddy.jpg" alt="DB Track Monitor & Navigator-Buddy Banner" width="100%">
</p>

# Hermes DB Agent & Discord Monitor

An automated, AI-augmented rail monitoring and assistant system built on top of [Hermes Agent](https://github.com/NousResearch/hermes-agent) and deployed on a Hostinger KVM VPS.

This solution monitors German railway (Deutsche Bahn) operations,specifically the regional transit corridor of **(RE5 / S-Bahn)**, pushing disruption alerts directly to Discord while serving live route queries with strict topic guardrails.

---

## Architecture Overview

The system runs two distinct Discord bot identities through a unified multi-profile Hermes deployment:

1. **Bahn-Assistent (Admin & Cron Bot)**
   - Located in the private `#baustellen-und-stoerungen` channel.
   - Executes scheduled tasks (delays every 30 minutes, construction updates twice daily).
   - Serves as the primary operational terminal for administrative tasks.
2. **Navigator-Buddy (Community Bot)**
   - Located in the public `#bahn-terminal` channel for server members.
   - Provides on-demand route, track, and timetable inquiries.
   - Enforces strict guardrails (rejects non-rail queries like weather, coding, or chit-chat).

```
                      +-----------------------------+
                      |             KVM VPS         |
                      |      (Ubuntu 26.04 LTS)     |
                      +--------------+--------------+
                                     |
              +----------------------+----------------------+
              |                                             |
   [ hermes.service (systemd) ]                [ Python Monitor Script ]
   Hermes Multi-Profile Gateway                 (Runs via Cron / CLI)
              |                                             |
     +--------+--------+                           +--------+--------+
     |                 |                           |                 |
Profile: default   Profile: navigator        IRIS API          DB Bauinfos
(Bahn-Assistent)   (Navigator-Buddy)      (bahn.expert)     (verkehrslage)
     |                 |                           |                 |
     +--------+--------+                           +--------+--------+
              |                                             |
              v                                             v
     Discord WebSocket Gateway                     Discord Webhook / Channel
    (#baustellen-und-stoerungen)                         (#bahn-terminal)
```

---

## Infrastructure Hardening

The VPS runs isolated with minimal attack surfaces:

- **SSH Hardening:** public key authentication only; password login disabled (`PasswordAuthentication no`).
- **Firewall (UFW):**
  - Incoming traffic: Denied by default (`default deny incoming`).
  - Outgoing traffic: Permitted for API and WebSocket connectivity (`default allow outgoing`).
  - Ingress: Rate-limited SSH access (`ufw limit 22/tcp`).
- **Memory & Swap:** Configured with a 4 GB swapfile to prevent out-of-memory kernel locks during token spikes.

---

## Installation & Setup

### 1. Prerequisites & Dependencies

Install base packages and required Python libraries:

```bash
sudo apt update && sudo apt install -y curl git ufw fail2ban python3 python3-httpx python3-bs4
```

### 2. Hermes Agent CLI Setup

Install the official Hermes agent binary:

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

Configuration defaults:
- **Model:** `anthropic/claude-haiku-5.5` via OpenRouter (low latency, high tool-calling precision).
- **Runtime:** `Keep current (local)`.
- **Telemetry:** Disabled.

### 3. Multi-Bot Discord Configuration

#### Bot 1: Bahn-Assistent (Default Profile)
1. Run setup:
   ```bash
   hermes gateway setup
   ```
2. Enter the Discord bot token for *Bahn-Assistent*.
3. Add system prompt and guardrails to `~/.hermes/AGENTS.md` and `~/.hermes/SOUL.md`.

#### Bot 2: Navigator-Buddy (Navigator Profile)
1. Initialize the secondary profile:
   ```bash
   hermes profile create navigator
   hermes -p navigator gateway setup
   ```
2. Enter the bot token for *Navigator-Buddy*.
3. Add community prompts and strict response rules to `~/.hermes/profiles/navigator/AGENTS.md`:
   ```markdown
   # Role: Navigator-Buddy
   You are an exclusive timetable and connection assistant for Deutsche Bahn in the #bahn-terminal channel.
   
   Rules:
   - Answer ONLY train connections, platforms, cancellations, and DB disruptions in German.
   - Strictly refuse off-topic requests (e.g., weather, programming, generic chit-chat).
   - Primary sources: bahn.expert, verkehrslage.bahnhof.de, and bahn.de.
   ```

---

## 24/7 Service Automation (systemd)

To guarantee background persistence and avoid process conflicts, the gateway is managed by systemd:

Create `/etc/systemd/system/hermes.service`:

```ini
[Unit]
Description=Hermes Multi-Profile Gateway
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root
ExecStart=/root/.local/bin/hermes gateway run --replace
Restart=always
RestartSec=10
TimeoutStartSec=infinity
TimeoutStopSec=30
Environment=PATH=/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now hermes
```

---

## Automated Monitoring (Cron Jobs)

The monitoring script `/root/db-monitor/monitor.py` handles API requests locally without burning LLM tokens. Deduplication is handled via local SQLite (`monitor_state.db`).

Register the scheduled jobs inside Hermes:

```bash
# Live delay and cancellation check every 30 minutes
hermes cron add --name "db-live-delay" --schedule "*/30 * * * *" --command "python3 /root/db-monitor/monitor.py delays"

# Construction site scan twice daily (06:00 and 18:00)
hermes cron add --name "db-baustellen" --schedule "0 6,18 * * *" --command "python3 /root/db-monitor/monitor.py construction"
```

Verify active jobs:

```bash
hermes cron list
```