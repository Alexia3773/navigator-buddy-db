# Step-by-Step Guide: Rail Monitor & Discord Assistant

---

## 1. Project Background & Motivation

Anyone who regularly commutes by train—especially on corridors like the **RE5** or the S-Bahn network around Hamburg and the Niederelbebahn—knows the daily frustration:
* Trains get cancelled at the last minute or accumulate substantial delays.
* Station announcements arrive late, contradict each other, or are missing altogether.
* Transit apps often reflect disruption statuses only after passengers are already waiting on the platform.

Driven by recurring dissatisfaction with fragmented, delayed passenger communication, this project was built to address that exact problem: **An automated, self-hosted rail operations watchdog that captures dispatch and construction data directly at the source, alerting commuters proactively before leaving home.**

---

## 2. System Architecture & Overview

The system runs on a Linux KVM VPS (Hostinger) under Ubuntu LTS, serving two distinct Discord bot identities via a unified, multiplexed **Hermes Agent Framework** gateway:

1. **Bahn-Assistent (Admin & Alerting Bot):**
   * **Channel:** `#baustellen-und-störungen` (private channel, restricted to server administrators).
   * **Role:** Automated proactive monitoring of delays, cancellations, and construction work via scheduled Hermes AI Agent cron jobs.
   * **Intelligence:** Employs **Claude Haiku 5.5** equipped with live web tools to dynamically inspect `bahn.expert`, `verkehrslage.bahnhof.de`, and `bauinfos.deutschebahn.com`, summarizing actionable travel advisories directly for commuters.

2. **Navigator-Buddy (Community Transit Assistant):**
   * **Channel:** `#bahn-terminal` (public channel accessible to all server members).
   * **Role:** Answers real-time passenger inquiries regarding timetables, platforms, connections, and route transfers.
   * **Guardrails:** Strict boundary prompts reject off-topic inquiries (weather, coding questions, general chit-chat).

```text
                          +-----------------------------+
                          |      Hostinger KVM VPS      |
                          |   Ubuntu LTS (UFW / SSH)    |
                          +--------------+--------------+
                                         |
                       +-----------------+-----------------+
                       |    Hermes Multiplex Gateway       |
                       |    (systemd: hermes.service)      |
                       +--------+---------------+---------+
                                |               |
             +------------------+               +------------------+
             v                                                     v
   [ Profile: default ]                                  [ Profile: navigator ]
      Bahn-Assistent                                        Navigator-Buddy
   #baustellen-und-störungen                                #bahn-terminal
   (Private / Cron / Alerts)                               (Public / Community)
```

---

## 3. Phase 1: Host Preparation & Infrastructure Hardening

### 3.1 Base Packages & Tooling Setup

Install the necessary system packages, Python runtime libraries, and security utilities on the VPS:

```bash
sudo apt update && sudo apt install -y curl git python3 python3-pip python3-httpx python3-bs4 ufw fail2ban unattended-upgrades
```

### 3.2 UFW Firewall & Attack Surface Minimization

Because outbound WebSockets and HTTPS clients manage Discord and API communication, all unsolicited inbound connections except rate-limited SSH are dropped:

```bash
# Block all incoming traffic by default, allow outbound connections
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Rate-limit SSH ingress to defend against brute-force attacks
sudo ufw limit 22/tcp comment 'SSH Ingress'

# Enable the firewall
sudo ufw --force enable

# Inspect status
sudo ufw status verbose
```

### 3.3 SSH Keypair Setup & Password Authentication Lockdown

Ed25519 keypairs are generated locally on client machines and deployed to the host:

* **EndeavourOS / Linux:**
  ```bash
  ssh-keygen -t ed25519 -C "endeavour-hermes"
  ssh-copy-id root@<YOUR_VPS_IP>
  ```

* **Windows 11 (PowerShell):**
  ```powershell
  ssh-keygen -t ed25519 -C "win11-hermes"
  Get-Content ~\.ssh\id_ed25519.pub
  ```
  *(Append the output key to `~/.ssh/authorized_keys` on the VPS)*

Once key-based authentication is confirmed working, disable password logins across the server:

```bash
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

---

## 4. Phase 2: Discord Application & Bot Registration

### 4.1 Bot 1: Creating "Bahn-Assistent"

1. Open the [Discord Developer Portal](https://discord.com/developers/applications) and create an application named `Bahn-Assistent`.
2. Navigate to the **Bot** tab:
   * Disable the **Public Bot** toggle to prevent unauthorized third-party invites.
   * Enable the **Message Content Intent** toggle under *Privileged Gateway Intents*.
3. Under the **Installation** menu, set the default authorization install link to *None* to prevent validation warnings.
4. Go to **OAuth2 > URL Generator**, check the `bot` scope with permissions to send messages, read message history, and embed links, then authorize the bot into your private `#baustellen-und-störungen` channel.
5. Copy the generated Bot Token.

### 4.2 Bot 2: Creating "Navigator-Buddy"

1. Create a second application named `Navigator-Buddy`.
2. Mirror the permission setup: **Public Bot** disabled, **Message Content Intent** enabled.
3. Generate the OAuth2 invite link and invite the bot to the server, assigning it to `#bahn-terminal`.
4. Copy the second Bot Token.

---

## 5. Phase 3: Hermes Agent Multi-Profile Setup & Guardrail Configuration

### 5.1 Hermes CLI Installation

Install the official Hermes agent binary:

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

* **Model Engine:** `anthropic/claude-haiku-5.5` via OpenRouter.
* **Execution Environment:** `Keep current (local)`.
* **Telemetry:** `No thanks`.

### 5.2 Configuring the Default Profile (Bahn-Assistent)

Run the gateway setup wizard for the default profile:

```bash
hermes gateway setup
```

* Select **Discord** as the platform.
* Paste the bot token for *Bahn-Assistent*.
* Set the security allowlist to your personal Discord User ID.
* In the Discord channel `#baustellen-und-störungen`, execute `/set-home` using Bahn-Assistent to set the home channel.

### 5.3 Initializing the Secondary Profile (Navigator-Buddy)

Provision an isolated secondary profile environment:

```bash
# Register profile
hermes profile create navigator

# Inherit API credentials and environment configuration
cp ~/.hermes/.env ~/.hermes/profiles/navigator/.env

# Configure the gateway connection for the secondary profile
hermes -p navigator gateway setup
```

* Supply the bot token for *Navigator-Buddy*.
* Leave the user allowlist open to allow all server members to query the bot in `#bahn-terminal`.
* Inside `#bahn-terminal`, execute `/set-home` via *Navigator-Buddy*.

### 5.4 Enforcing Topic Guardrails

To prevent off-topic LLM token usage and ensure strict rail-only domain focus:

* **Navigator-Buddy (`~/.hermes/profiles/navigator/AGENTS.md`):**

```text
# Role: Navigator-Buddy
You are the dedicated passenger transit assistant for Deutsche Bahn in the #bahn-terminal Discord channel.

Rules:
1. Answer ONLY train schedules, departures, platform designations, cancellations, and rail disruptions in German.
2. Strictly refuse all non-rail inquiries (weather, general programming, casual chit-chat, jokes) using the following fallback response:
   "Hallo! Als Navigator-Buddy helfe ich euch exklusiv bei Fahrplänen und Verbindungen der Deutschen Bahn. Stelle mir gerne eine Frage zu deiner nächsten Zugfahrt!"
3. Authorized information sources: bahn.expert, bahn.de, verkehrslage.bahnhof.de.
```

*(Synchronize prompt files: `cp AGENTS.md SOUL.md`)*

* **Bahn-Assistent (`~/.hermes/AGENTS.md`):**

```text
# Role: Bahn-Assistent
You are the internal operations and infrastructure monitoring bot in the #baustellen-und-störungen channel.
Respond exclusively to rail operations queries and reject general conversation.
```

### 5.5 Multiplexing Migration

Consolidate both profiles onto a single host daemon to prevent socket collisions:

```bash
hermes gateway migrate --multiplex
```

---

## 6. Phase 4: Local Inspection Engine (`monitor.py`)

Located at `/root/db-monitor/monitor.py`, this zero-token monitoring engine queries the IRIS departure API and official construction feeds, deduplicating alerts using local SQLite storage (`monitor_state.db`).

Monitored stations along the target commuter corridor (RE5 / S-Bahn):
* Cuxhaven (8001384)
* Otterndorf (8004738)
* Hamburg-Neugraben (8002553)
* Hamburg-Harburg (8002548)
* Hamburg Hbf (8002549)

### Manual Engine Validation

```bash
# 1. Test live departure delay checks
python3 /root/db-monitor/monitor.py delays

# 2. Test construction and trackwork parser
python3 /root/db-monitor/monitor.py construction
```

---

## 7. Phase 5: Scheduled Automation (Autonomous AI Agent Cron Jobs)

Instead of relying on brittle static scripts, Hermes runs scheduled **AI Agent tasks powered by Claude Haiku 5.5**. During designated commuter windows, the agent autonomously queries `bahn.expert`, `verkehrslage.bahnhof.de`, and `bauinfos.deutschebahn.com` using native web tools, evaluates operational conditions against defined thresholds (delays $\ge$ 5 min, cancellations, track changes, or rail replacement services), and delivers concise status digests straight into Discord.

### 7.1 Defining Agent Directives (`~/.hermes/AGENTS.md`)
Configure the agent's inspection instructions and source priorities in `~/.hermes/AGENTS.md`:
```markdown
# Role: Railway Assistant
You are the dedicated railway monitor for the Hamburg ⇄ Cuxhaven commuter route (RE5 / Niederelbebahn), operating within the #baustellen-und-störungen Discord channel.

## Monitored Stations & Route Section:
- Hamburg Hbf, Hamburg-Harburg, Hamburg-Neugraben, Buxtehude, Stade, Otterndorf, Cuxhaven.

## Data Sources & Web Tools:
- Live operational status & disruptions: [https://verkehrslage.bahnhof.de](https://verkehrslage.bahnhof.de) and [https://bahn.expert](https://bahn.expert) (RE5 / S-Bahn departures).
- Construction work, replacement services, & schedule changes: [https://bauinfos.deutschebahn.com](https://bauinfos.deutschebahn.com)

## Guidelines for Automated (Cron) Updates:
1. Use your web tools to retrieve the latest data from the specified sources.
2. Filtering: Include only disruptions, cancellations, or delays of 5 minutes or more, as well as upcoming or ongoing construction work affecting this route.
3. If everything is running on time and without issues: Provide a very brief response: "✅ No disruptions on the Hamburg ⇄ Cuxhaven route."
4. If there are disruptions or construction work: Summarize the train number, affected section, delay/cancellation, and cause—using clear, concise bullet points.

## 7.2 Registering Autonomous Agent Cron Jobs

### 1. Early morning commuter check (04:00)
hermes cron create "0 4 * * *" \
  --name "agent-morning-check" \
  --deliver discord \
  "Prüfe die aktuelle Betriebslage für den RE5 zwischen Cuxhaven und Hamburg Hbf auf bahn.expert und verkehrslage.bahnhof.de. Melde Verspätungen ab 5 Minuten oder Zugausfälle für die morgendlichen Pendler."

### 2. Afternoon rush-hour window every 30 minutes (15:00 to 17:00)
hermes cron create "0,30 15-17 * * *" \
  --name "agent-rushhour-check" \
  --deliver discord \
  "Prüfe die aktuelle Betriebslage für den RE5 zwischen Hamburg Hbf und Cuxhaven auf bahn.expert. Melde akute Verspätungen ab 5 Minuten, Teilausfälle oder Gleiswechsel für den Feierabendverkehr."

### 3. Trackwork & infrastructure scan twice daily (04:05 and 15:05)
hermes cron create "5 4,15 * * *" \
  --name "agent-baustellen-scan" \
  --deliver discord \
  "Prüfe auf bauinfos.deutschebahn.com und verkehrslage.bahnhof.de alle aktiven und anstehenden Baustellen oder SEV-Maßnahmen für die Strecke RE5 Hamburg ⇄ Cuxhaven. Fasse die Einschränkungen für Pendler übersichtlich zusammen."

  ## 7.3 Verifying Schedules and Running Immediate Tests

### List active agent schedules
hermes cron list

### Manually trigger an immediate test run
hermes cron run agent-rushhour-check  

---

## 8. Phase 6: Continuous Background Execution (systemd)

To guarantee background persistence across reboots and process failures, configure the systemd unit:

File: `/etc/systemd/system/hermes.service`

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

Reload, enable, and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now hermes
sudo systemctl status hermes
```

---

## 9. Troubleshooting & Operational Commands

| Objective | Command |
|---|---|
| Check multiplexed gateway status | `hermes gateway status` |
| Follow live service logs | `journalctl -u hermes -f` |
| List active cron tasks | `hermes cron list` |
| Manually trigger a scheduled job | `hermes cron run <JOB_NAME_OR_ID>` |
| Check VPS memory and CPU usage | `htop` or `free -m` |
