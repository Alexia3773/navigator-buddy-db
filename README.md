
<p align="center">
<img src="assets\DB-Nav-Buddy.jpg" alt="DB Track Monitor & Navigator-Buddy Banner" width="100%">
<sub><em>Banner illustration generated with AI (Google Gemini ImageFX). All rights and trademarks (DB, Deutsche Bahn) belong to their respective owners.</em></sub>
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
                      |      (Ubuntu 24.04 LTS)     |
                      +--------------+--------------+
                                     |
              +----------------------+----------------------+
              |                                             |
   [ hermes.service (systemd) ]                [ Hermes Agent Scheduler ]
   Hermes Multi-Profile Gateway                 (Runs Prompts via Cron)
              |                                             |
     +--------+--------+                           +--------+--------+
     |                 |                           |                 |
Profile: default   Profile: navigator        Claude Haiku 5.5   Web Tools
(Bahn-Assistent)   (Navigator-Buddy)        (Tool-Calling AI) (Search/Extract)
     |                 |                           |                 |
     +--------+--------+                           +--------+--------+
              |                                             |
              v                                             v
     Discord WebSocket Gateway                     Discord Channels
    (#baustellen-und-stoerungen)             (#baustellen-und-stoerungen)
                                                   (#bahn-terminal)

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

## Automated Monitoring (Autonomous Agent Cron Jobs)

Monitoring is powered directly by **Claude Haiku 5.5** running within the Hermes Agent framework. Instead of static script parsing, Hermes executes periodic prompt-based jobs where the AI autonomously navigates real-time feeds (e.g. `bahn.expert`, `verkehrslage.bahnhof.de`, and `bauinfos.deutschebahn.com`) using web search and extraction tools, verifies disruption thresholds (delays $\ge$ 5 min, cancellations, track work), formats commuter digests, and pushes alerts directly to Discord.

Rules and source constraints for automated scans are defined in `~/.hermes/AGENTS.md`.

The autonomous jobs are scheduled directly inside the Hermes scheduler:

```bash
# 1. Early morning commuter check (04:00)
hermes cron create "0 4 * * *" \
  --name "agent-morning-check" \
  --deliver discord \
  "Prüfe die aktuelle Betriebslage für den RE5 zwischen Cuxhaven und Hamburg Hbf auf bahn.expert und verkehrslage.bahnhof.de. Melde Verspätungen ab 5 Minuten oder Zugausfälle für die morgendlichen Pendler."

# 2. Afternoon rush-hour window every 30 minutes (15:00 to 17:00)
hermes cron create "0,30 15-17 * * *" \
  --name "agent-rushhour-check" \
  --deliver discord \
  "Prüfe die aktuelle Betriebslage für den RE5 zwischen Hamburg Hbf und Cuxhaven auf bahn.expert. Melde akute Verspätungen ab 5 Minuten, Teilausfälle oder Gleiswechsel für den Feierabendverkehr."

# 3. Construction & infrastructure scan twice daily (04:05 and 15:05)
hermes cron create "5 4,15 * * *" \
  --name "agent-baustellen-scan" \
  --deliver discord \
  "Prüfe auf bauinfos.deutschebahn.com und verkehrslage.bahnhof.de alle aktiven und anstehenden Baustellen oder SEV-Maßnahmen für die Strecke RE5 Hamburg ⇄ Cuxhaven. Fasse die Einschränkungen für Pendler übersichtlich zusammen."