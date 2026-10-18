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
   * **Channel:** `#baustellen-und-störungen` (private channel, restricted to server administrators)[cite: 1, 4].
   * **Role:** Automated event alerts covering delays, train cancellations, and track work via scheduled cron jobs[cite: 1, 4].
   * **Efficiency:** Executes tasks locally using zero-token execution mode (`--no-agent`), ensuring scheduled background scans consume no LLM API tokens[cite: 1, 4].

2. **Navigator-Buddy (Community Transit Assistant):**
   * **Channel:** `#bahn-terminal` (public channel accessible to all server members)[cite: 1, 4].
   * **Role:** Answers real-time passenger inquiries regarding timetables, platforms, connections, and route transfers[cite: 1, 4].
   * **Guardrails:** Strict boundary prompts reject off-topic inquiries (weather, coding questions, general chit-chat)[cite: 1, 4].

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
```[cite: 1, 4]

---

## 3. Phase 1: Host Preparation & Infrastructure Hardening

### 3.1 Base Packages & Tooling Setup
Install the necessary system packages, Python runtime libraries, and security utilities on the VPS[cite: 1, 4]:
```bash
sudo apt update && sudo apt install -y curl git python3 python3-pip python3-httpx python3-bs4 ufw fail2ban unattended-upgrades
```[cite: 1, 4]

### 3.2 UFW Firewall & Attack Surface Minimization
Because outbound WebSockets and HTTPS clients manage Discord and API communication, all unsolicited inbound connections except rate-limited SSH are dropped[cite: 1, 4]:
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
```[cite: 1, 4]

### 3.3 SSH Keypair Setup & Password Authentication Lockdown
Ed25519 keypairs are generated locally on client machines and deployed to the host[cite: 1, 4]:
* **EndeavourOS / Linux:**
  ```bash
  ssh-keygen -t ed25519 -C "endeavour-hermes"
  ssh-copy-id root@<YOUR_VPS_IP>
  ```[cite: 1, 4]
* **Windows 11 (PowerShell):**
  ```powershell
  ssh-keygen -t ed25519 -C "win11-hermes"
  Get-Content ~\.ssh\id_ed25519.pub
  ```[cite: 4]
  *(Append the output key to `~/.ssh/authorized_keys` on the VPS)*[cite: 4]

Once key-based authentication is confirmed working, disable password logins across the server[cite: 1, 4]:
```bash
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```[cite: 1, 4]

---

## 4. Phase 2: Discord Application & Bot Registration

### 4.1 Bot 1: Creating "Bahn-Assistent"
1. Open the [Discord Developer Portal](https://discord.com/developers/applications) and create an application named `Bahn-Assistent`[cite: 2, 4].
2. Navigate to the **Bot** tab[cite: 2, 4]:
   * Disable the **Public Bot** toggle to prevent unauthorized third-party invites[cite: 2, 4].
   * Enable the **Message Content Intent** toggle under *Privileged Gateway Intents*[cite: 2, 4].
3. Under the **Installation** menu, set the default authorization install link to *None* to prevent validation warnings.
4. Go to **OAuth2 > URL Generator**, check the `bot` scope with permissions to send messages, read message history, and embed links[cite: 4], then authorize the bot into your private `#baustellen-und-störungen` channel[cite: 1, 4].
5. Copy the generated Bot Token[cite: 2, 4].

### 4.2 Bot 2: Creating "Navigator-Buddy"
1. Create a second application named `Navigator-Buddy`[cite: 4].
2. Mirror the permission setup: **Public Bot** disabled, **Message Content Intent** enabled[cite: 2, 4].
3. Generate the OAuth2 invite link and invite the bot to the server, assigning it to `#bahn-terminal`[cite: 1, 4].
4. Copy the second Bot Token[cite: 2, 4].

---

## 5. Phase 3: Hermes Agent Multi-Profile Setup & Guardrail Configuration

### 5.1 Hermes CLI Installation
Install the official Hermes agent binary[cite: 1, 4]:
```bash
curl -fsSL [https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh](https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh) | bash
```[cite: 1, 4]
* **Model Engine:** `anthropic/claude-haiku-5.5` via OpenRouter[cite: 1, 4].
* **Execution Environment:** `Keep current (local)`[cite: 1, 4].
* **Telemetry:** `No thanks`[cite: 1, 4].

### 5.2 Configuring the Default Profile (Bahn-Assistent)
Run the gateway setup wizard for the default profile[cite: 1, 4]:
```bash
hermes gateway setup
```[cite: 1, 4]
* Select **Discord** as the platform[cite: 2, 4].
* Paste the bot token for *Bahn-Assistent*[cite: 1, 4].
* Set the security allowlist to your personal Discord User ID[cite: 2, 4].
* In the Discord channel `#baustellen-und-störungen`, execute `/set-home` using Bahn-Assistent to set the home channel[cite: 2, 4].

### 5.3 Initializing the Secondary Profile (Navigator-Buddy)
Provision an isolated secondary profile environment[cite: 2, 4]:
```bash
# Register profile
hermes profile create navigator

# Inherit API credentials and environment configuration
cp ~/.hermes/.env ~/.hermes/profiles/navigator/.env

# Configure the gateway connection for the secondary profile
hermes -p navigator gateway setup
```[cite: 2, 4]
* Supply the bot token for *Navigator-Buddy*[cite: 2, 4].
* Leave the user allowlist open to allow all server members to query the bot in `#bahn-terminal`[cite: 2, 4].
* Inside `#bahn-terminal`, execute `/set-home` via *Navigator-Buddy*[cite: 2, 4].

### 5.4 Enforcing Topic Guardrails

To prevent off-topic LLM token usage and ensure strict rail-only domain focus[cite: 1, 2]:

* **Navigator-Buddy (`~/.hermes/profiles/navigator/AGENTS.md`):**
```text
# Role: Navigator-Buddy
You are the dedicated passenger transit assistant for Deutsche Bahn in the #bahn-terminal Discord channel.

Rules:
1. Answer ONLY train schedules, departures, platform designations, cancellations, and rail disruptions in German.
2. Strictly refuse all non-rail inquiries (weather, general programming, casual chit-chat, jokes) using the following fallback response:
   "Hallo! Als Navigator-Buddy helfe ich euch exklusiv bei Fahrplänen und Verbindungen der Deutschen Bahn. Stelle mir gerne eine Frage zu deiner nächsten Zugfahrt!"
3. Authorized information sources: bahn.expert, bahn.de, verkehrslage.bahnhof.de.
```[cite: 2, 3]
*(Synchronize prompt files: `cp AGENTS.md SOUL.md`)*[cite: 2, 3]

* **Bahn-Assistent (`~/.hermes/AGENTS.md`):**
```text
# Role: Bahn-Assistent
You are the internal operations and infrastructure monitoring bot in the #baustellen-und-störungen channel.
Respond exclusively to rail operations queries and reject general conversation.
```[cite: 1, 3]

### 5.5 Multiplexing Migration
Consolidate both profiles onto a single host daemon to prevent socket collisions[cite: 1, 4]:
```bash
hermes gateway migrate --multiplex
```[cite: 1, 4]

---

## 6. Phase 4: Local Inspection Engine (`monitor.py`)

Located at `/root/db-monitor/monitor.py`, this zero-token monitoring engine queries the IRIS departure API and official construction feeds, deduplicating alerts using local SQLite storage (`monitor_state.db`)[cite: 1, 4].

Monitored stations along the target commuter corridor (RE5 / S-Bahn)[cite: 1, 4]:
* Cuxhaven (8001384)[cite: 1, 4]
* Otterndorf (8004738)[cite: 1, 4]
* Hamburg-Neugraben (8002553)[cite: 1, 4]
* Hamburg-Harburg (8002548)[cite: 1, 4]
* Hamburg Hbf (8002549)[cite: 1, 4]

### Manual Engine Validation
```bash
# 1. Test live departure delay checks
python3 /root/db-monitor/monitor.py delays

# 2. Test construction and trackwork parser
python3 /root/db-monitor/monitor.py construction
```[cite: 1, 4]

---

## 7. Phase 5: Scheduled Automation (Hermes Cron Scheduler)

To keep monitoring tasks token-free (`--no-agent`), lightweight Python wrappers are placed under `~/.hermes/scripts/`[cite: 1, 4]:

```bash
mkdir -p ~/.hermes/scripts

# Create delays wrapper
cat << 'EOF' > ~/.hermes/scripts/check_delays.py
import subprocess, sys
res = subprocess.run([sys.executable, "/root/db-monitor/monitor.py", "delays"], capture_output=True, text=True)
if res.stdout.strip() and "Keine neuen Verspätungen" not in res.stdout:
    print(res.stdout.strip())
EOF

# Create construction wrapper
cat << 'EOF' > ~/.hermes/scripts/check_construction.py
import subprocess, sys
res = subprocess.run([sys.executable, "/root/db-monitor/monitor.py", "construction"], capture_output=True, text=True)
if res.stdout.strip() and "Keine neuen Baustellenmeldungen" not in res.stdout:
    print(res.stdout.strip())
EOF

chmod +x ~/.hermes/scripts/*.py
```[cite: 1]

### Registering Cron Schedules
```bash
# 1. Early morning commuter check (04:00)
hermes cron create "0 4 * * *" \
  --name "db-delay-morning" \
  --script "check_delays.py" \
  --no-agent \
  --deliver discord

# 2. Afternoon rush-hour window every 30 minutes (15:00 to 17:00)
hermes cron create "0,30 15-17 * * *" \
  --name "db-delay-rushhour" \
  --script "check_delays.py" \
  --no-agent \
  --deliver discord

# 3. Trackwork and infrastructure scan twice daily (04:05 and 15:05)
hermes cron create "5 4,15 * * *" \
  --name "db-baustellen" \
  --script "check_construction.py" \
  --no-agent \
  --deliver discord
```[cite: 1]

Verify active cron jobs[cite: 1, 4]:
```bash
hermes cron list
```[cite: 1, 4]

---

## 8. Phase 6: Continuous Background Execution (systemd)

To guarantee background persistence across reboots and process failures, configure the systemd unit[cite: 1, 4]:

File: `/etc/systemd/system/hermes.service`[cite: 1, 4]
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
```[cite: 1, 4]

Reload, enable, and start the service[cite: 1, 4]:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now hermes
sudo systemctl status hermes
```[cite: 1, 4]

---

## 9. Troubleshooting & Operational Commands

| Objective | Command |
|---|---|
| Check multiplexed gateway status | `hermes gateway status`[cite: 1, 4] |
| Follow live service logs | `journalctl -u hermes -f`[cite: 1] |
| List active cron tasks | `hermes cron list`[cite: 1, 4] |
| Manually trigger a scheduled job | `hermes cron run <JOB_NAME_OR_ID>`[cite: 1] |
| Check VPS memory and CPU usage | `htop` or `free -m`[cite: 1] |
