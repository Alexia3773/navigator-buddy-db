<p align="center">
<img src="assets/DB-Nav-Buddy.jpg" alt="DB Track Monitor & Navigator-Buddy Banner" width="100%"><br>
<sub><em>Banner illustration generated with AI (Google Gemini ImageFX). All rights and trademarks (DB, Deutsche Bahn) belong to their respective owners.</em></sub>
</p>

# Hermes DB Agent & Discord Monitor

An automated, AI-augmented rail monitoring and assistant system built on top of [Hermes Agent](https://github.com/NousResearch/hermes-agent) and deployed on a Linux KVM VPS.

This solution monitors German railway (Deutsche Bahn) operations, specifically the regional commuter corridor of the **Niederelbebahn (RE 5: Hamburg ⇄ Cuxhaven)** and surrounding transit hubs (Hamburg Hbf, Hamburg-Harburg, Hamburg-Neugraben, Buxtehude, Stade, Otterndorf, Cuxhaven). It pushes automated disruption alerts directly to Discord while serving live connection and schedule queries with strict topic guardrails.

---

## Architecture Overview

The system runs two distinct Discord bot identities through a unified multi-profile Hermes deployment:

1. **Bahn-Assistent (Admin & Alerting Bot)**
   - Located in the private `#baustellen-und-störungen` channel.
   - Executes autonomous scheduled tasks (morning checks, rush-hour monitoring every 30 minutes, and twice-daily construction scans).
   - Serves as the operational alert feed for line incidents, acute delays, and track changes.

2. **Navigator-Buddy (Community Transit Assistant)**
   - Located in the public `#bahn-terminal` channel for server members.
   - Provides interactive live timetable, track, and route guidance.
   - Enforces strict guardrails (rejects off-topic queries such as general chit-chat, coding, or unrelated weather).

```text
                      +-----------------------------+
                      |         Linux KVM VPS       |
                      |      (Ubuntu 24.04 LTS)     |
                      +--------------+--------------+
                                     |
              +----------------------+----------------------+
              |                                             |
   [ hermes.service (systemd) ]                [ Hermes Agent Scheduler ]
   Hermes Multi-Profile Gateway                 (Autonomous Cron Prompts)
              |                                             |
     +--------+--------+                           +--------+--------+
     |                 |                           |                 |
Profile: default   Profile: navigator        Claude Haiku 5.5   Web Tools
(Bahn-Assistent)   (Navigator-Buddy)        (Tool-Calling AI) (Live IRIS & Delaybahn)
     |                 |                           |                 |
     +--------+--------+                           +--------+--------+
              |                                             |
              v                                             v
     Discord WebSocket Gateway                     Discord Channels
    (#baustellen-und-störungen)              (#baustellen-und-störungen)
                                                   (#bahn-terminal)
```

---

## Data Strategy: Migration from `bahn.expert` to IRIS & Delaybahn

Due to snapshot limits, dynamic SPA rendering, and timezone ambiguities when querying single-page applications like `bahn.expert`, the system was migrated to a resilient dual-source approach:

1. **Live Station Boards via Official DB IRIS (`iris.noncd.db.de`)**
   - **Purpose:** Source of truth for real-time delays, acute cancellations, and platform/track changes.
   - **Advantage:** Directly hosted by Deutsche Bahn, ultra-lightweight, high availability, and not dependent on client-side JavaScript rendering.
   - **Station Identifiers:** Lookups utilize standard DB DS100/Ril100 station codes (e.g., `AH` for Hamburg Hbf, `AHAR` for Harburg, `ABX` for Buxtehude, `AST` for Stade, `ACX` for Cuxhaven).

2. **Structured Journey Routing via Delaybahn (`delaybahn.com`)**
   - **Purpose:** Point-to-point journey queries, intermediate stops, and timetables.
   - **Advantage:** Supports explicit URL-level query parameters (`fromId`, `toId`, `date`, `time`, `window`), allowing the agent to evaluate specific commuter departure windows directly.
   - **Strict Real-Time Guardrail:** Historical 7-day performance metrics from Delaybahn are treated strictly as secondary historical statistics—never confused with today's real-time operational status.

3. **Construction & Infrastructure Feeds**
   - Official regional summaries from `bauinfos.deutschebahn.com` and `verkehrslage.bahnhof.de` (DB Regio Nord).

---

## Infrastructure Hardening

The VPS runs isolated with minimal attack surfaces:

- **SSH Hardening:** Public key authentication only (Ed25519); password login disabled (`PasswordAuthentication no`).
- **Firewall (UFW):**
  - Incoming traffic: Denied by default (`default deny incoming`).
  - Outgoing traffic: Permitted for WebSocket and API connectivity (`default allow outgoing`).
  - Ingress: Rate-limited SSH access (`ufw limit 22/tcp`).
- **Memory & Swap:** Configured with a 4 GB swapfile to ensure system stability during heavy background jobs.
- **Maintenance:** Automated security patching via `unattended-upgrades` and intrusion prevention via `fail2ban`.

---

## Installation & Setup

### 1. Prerequisites & Dependencies

Install base packages and required tools:

```bash
sudo apt update && sudo apt install -y curl git ufw fail2ban python3 python3-pip
```

### 2. Hermes Agent CLI Setup

Install the official Hermes agent binary:

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

Configuration defaults:
- **Model:** `anthropic/claude-haiku-5.5` via OpenRouter.
- **Runtime:** Local gateway mode.

### 3. Multi-Profile Setup

#### Profile 1: Bahn-Assistent (Default Profile)

```bash
hermes gateway setup
```

- Configure the Discord bot token for *Bahn-Assistent*.
- Dedicated operational scope: `#baustellen-und-störungen`.

#### Profile 2: Navigator-Buddy (Navigator Profile)

```bash
hermes profile create navigator
hermes -p navigator gateway setup
```

- Configure the Discord bot token for *Navigator-Buddy*.
- Public scope: `#bahn-terminal` (supports multilingual queries, strict rail-only topic filtering, and rate-limiting).

---

## 24/7 Service Automation (systemd)

The multi-profile gateway runs as a resilient background daemon managed by systemd:

`/etc/systemd/system/hermes.service`:

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

## Autonomous Monitoring (Scheduled Tasks)

Instead of relying on brittle local scrapers, monitoring tasks run as prompt-driven autonomous agent jobs using **Claude Haiku 5.5** inside the Hermes Scheduler. The agent evaluates the live IRIS departure boards and Delaybahn routes, filters for delays $\ge$ 5 minutes, track changes, or cancellations on the RE 5 line, and pushes concise reports to Discord:

```bash
# 1. Morning commuter check (04:30 German time / Cuxhaven & Stade -> Hamburg Hbf)
hermes cron create "30 4 * * *" \
  --name "agent-morning-check" \
  --deliver discord \
  "Check live IRIS boards for Cuxhaven (ACX) and Stade (AST) for RE 5 heading to Hamburg Hbf between 04:30 and 07:00. Report delays >= 5 min or cancellations. Max 40 words."

# 2. Rush-hour check (15:00 to 17:30 German time every 30 min / Hamburg -> Cuxhaven)
hermes cron create "0,30 15,16,17 * * *" \
  --name "agent-rushhour-check" \
  --deliver discord \
  "Check live IRIS boards for Hamburg Hbf (AH), Harburg (AHAR), Buxtehude (ABX), and Stade (AST) for RE 5 heading to Cuxhaven for the next hour. Report delays >= 5 min, track changes, or cancellations. Max 40 words."

# 3. Construction & replacement service scan (04:05 & 15:05 German time)
hermes cron create "5 4,15 * * *" \
  --name "agent-baustellen-scan" \
  --deliver discord \
  "Check DB Regio Nord construction reports for RE 5 Hamburg <-> Cuxhaven. Summarize active disruptions and rail replacement services. Max 40 words."
```

*(Note: Adjust cron hours to UTC if the host VPS system clock is set to UTC).*