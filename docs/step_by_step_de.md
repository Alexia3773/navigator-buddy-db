# Schritt-für-Schritt-Anleitung: Bahn-Monitor & Discord-Assistent

---

## 1. Warum dieses Projekt entstanden ist (Motivation)

Jeder, der regelmäßig mit der Bahn pendelt – insbesondere auf Linien wie dem **RE5** oder im S-Bahn-Netz rund um Hamburg und die Niederelbebahn –, kennt das frustrierende Gefühl:
* Züge fallen kurzfristig aus oder sammeln massive Verspätungen an.
* Durchsagen am Bahnsteig erfolgen oft zu spät, widersprechen sich oder fehlen völlig.
* Fahrplan-Apps aktualisieren die Lage häufig erst dann, wenn man bereits frierend am Gleis steht.

Aus diesem ständigen Ärger über mangelnde und verspätete Kommunikation entstand die Idee für dieses Projekt: **Eine eigene, automatisierte Lösung, die Betriebs- und Baustellendaten direkt an der Quelle abfängt und mich proaktiv informiert, bevor ich das Haus verlasse.**

---

## 2. Architektur & Systemüberblick

Das System läuft auf einem Linux KVM VPS (Hostinger) unter Ubuntu LTS und kombiniert zwei spezialisierte Discord-Bots über das Multiplex-Gateway des **Hermes Agent Frameworks**:

1. **Bahn-Assistent (Admin- & Alarm-Bot):**
   * **Kanal:** `#baustellen-und-störungen` (privater Kanal, nur für Admins).
   * **Aufgabe:** Vollautomatische Meldungen bei Verspätungen/Ausfällen und Baustellen via Cronjobs.
   * **Ressourcen:** Arbeitet im Null-Token-Modus (`--no-agent`), wodurch keine laufenden KI-Kosten für Routine-Scans entstehen.

2. **Navigator-Buddy (Community-Reisebegleiter):**
   * **Kanal:** `#bahn-terminal` (öffentlich für alle Server-Mitglieder).
   * **Aufgabe:** Beantwortet Fragen zu Fahrzeiten, Gleisen, Verbindungen und Umstiegen auf Deutsch.
   * **Schutz:** Strikte Guardrails weisen bahnfremde Anfragen (Wetter, Smalltalk, Programmierung) konsequent ab.

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
     Bahn-Assistent                                         Navigator-Buddy
   #baustellen-und-störungen                                #bahn-terminal
   (Privat / Cron / Alarm)                                (Public / Community)
```

---

## 3. Phase 1: Server-Vorbereitung & Härtung

### 3.1 Basis-Pakete & Werkzeuge installieren
Auf dem VPS werden zunächst alle Abhängigkeiten für Python, Web-Scraping und Sicherheit installiert:
```bash
sudo apt update && sudo apt install -y curl git python3 python3-pip python3-httpx python3-bs4 ufw fail2ban unattended-upgrades
```

### 3.2 UFW-Firewall & Port-Minimierung
Da die Bots ausgehende WebSocket- und HTTPS-Verbindungen nutzen, werden sämtliche eingehenden Ports bis auf SSH blockiert:
```bash
# Eingehenden Datenverkehr sperren, ausgehenden erlauben
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH-Port mit Ratenbegrenzung gegen Brute-Force schützen
sudo ufw limit 22/tcp comment 'SSH Zugang'

# Firewall aktivieren
sudo ufw --force enable

# Status prüfen
sudo ufw status verbose
```

### 3.3 SSH-Schlüsselpaar einrichten & Passwort-Login deaktivieren
Schlüssel werden lokal auf den jeweiligen Rechnern erzeugt und übertragen:
* **EndeavourOS / Linux:**
  ```bash
  ssh-keygen -t ed25519 -C "endeavour-hermes"
  ssh-copy-id root@<DEINE_VPS_IP>
  ```
* **Windows 11 (PowerShell):**
  ```powershell
  ssh-keygen -t ed25519 -C "win11-hermes"
  Get-Content ~\.ssh\id_ed25519.pub
  ```
  *(Den Schlüssel auf dem VPS an `~/.ssh/authorized_keys` anfügen)*

Sobald der schlüssellose Login funktioniert, wird die Passwortanmeldung auf dem VPS gesperrt:
```bash
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

---

## 4. Phase 2: Discord Bots im Developer Portal anlegen

### 4.1 Bot 1: „Bahn-Assistent“ anlegen
1. Im [Discord Developer Portal](https://discord.com/developers/applications) eine neue Applikation namens `Bahn-Assistent` anlegen.
2. Unter **Bot**:
   * **Public Bot** deaktivieren (verhindert unbefugtes Einladen durch Dritte).
   * **Message Content Intent** unter *Privileged Gateway Intents* aktivieren.
3. Unter **Installation** den Standard-Autorisierungslink auf *Keine* setzen (Validierungsfehler vermeiden).
4. Über **OAuth2 > URL Generator** einen Link mit den Scopes `bot` und Rechten (Nachrichten senden, Nachrichtenverlauf lesen, Links einbetten) erzeugen und den Bot auf den eigenen Server in `#baustellen-und-störungen` einladen.
5. Das Bot-Token kopieren.

### 4.2 Bot 2: „Navigator-Buddy“ anlegen
1. Eine zweite Applikation namens `Navigator-Buddy` erstellen.
2. Identische Rechte vergeben: **Public Bot** aus, **Message Content Intent** an.
3. Über den URL-Generator auf den Discord-Server einladen und dem Kanal `#bahn-terminal` zuweisen.
4. Das zweite Bot-Token kopieren.

---

## 5. Phase 3: Hermes Agent Multi-Profile & Guardrails

### 5.1 Hermes CLI installieren
```bash
curl -fsSL [https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh](https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh) | bash
```
* **Modell:** `anthropic/claude-haiku-5.5` (via OpenRouter).
* **Backend:** `Keep current (local)`.
* **Telemetrie:** `No thanks`.

### 5.2 Standard-Profil (Bahn-Assistent) einrichten
```bash
hermes gateway setup
```
* Plattform: `Discord`
* Token: Token von *Bahn-Assistent* einfügen.
* Allowlist / Security: Eigenen Discord-Nutzer eintragen.
* Home Channel: Im Discord-Kanal `#baustellen-und-störungen` den Befehl `/set-home` ausführen.

### 5.3 Zweites Profil (Navigator-Buddy) anlegen
```bash
# Profil erstellen
hermes profile create navigator

# API-Keys und Umgebungsvariablen übernehmen
cp ~/.hermes/.env ~/.hermes/profiles/navigator/.env

# Gateway-Verbindung für das Profil konfigurieren
hermes -p navigator gateway setup
```
* Token von *Navigator-Buddy* eingeben.
* Allowlist leer lassen (alle Servermitglieder dürfen im Terminal fragen).
* Im Discord-Kanal `#bahn-terminal` den Befehl `/set-home` von *Navigator-Buddy* aufrufen.

### 5.4 Themenbeschränkungen (Guardrails) hinterlegen

Damit beide Bots ausschließlich Fragen zur Bahn beantworten und Kosten sparen:

* **Navigator-Buddy (`~/.hermes/profiles/navigator/AGENTS.md`):**
```text
# Rolle: Navigator-Buddy
Du bist der exklusive Fahrplan- und Reise-Assistent für die Deutsche Bahn im Kanal #bahn-terminal.

Regeln:
1. Beantworte AUSSCHLIESSLICH Fragen zu Zugverbindungen, Abfahrtszeiten, Bahnhöfen, Gleisen und Umstiegen der DB auf Deutsch.
2. Weise ALLE anderen Themen (Wetter, Witze, Programmierung, Smalltalk) strikt mit folgendem Satz ab:
   "Hallo! Als Navigator-Buddy helfe ich euch exklusiv bei Fahrplänen und Verbindungen der Deutschen Bahn. Stelle mir gerne eine Frage zu deiner nächsten Zugfahrt!"
3. Erlaubte Quellen: bahn.expert, bahn.de, verkehrslage.bahnhof.de.
```
*(Anschließend per `cp AGENTS.md SOUL.md` synchronisieren)*

* **Bahn-Assistent (`~/.hermes/AGENTS.md`):**
```text
# Rolle: Bahn-Assistent
Du bist der interne Betriebs- und Monitor-Assistent im Kanal #baustellen-und-störungen.
Reagiere nur auf betriebliche Bahnfragen und ignoriere bahnfremden Smalltalk.
```

### 5.5 Multiplexing aktivieren
Damit beide Profile über einen einzigen zentralen Hintergrundprozess betrieben werden:
```bash
hermes gateway migrate --multiplex
```

---

## 6. Phase 4: Lokales Überwachungs-Skript (`monitor.py`)

Unter `/root/db-monitor/monitor.py` liegt das Python-Skript, das über die IRIS-Schnittstelle und DB-Seiten Störungen abfragt und über SQLite (`monitor_state.db`) dedupliziert.

Überwachte Stationen:
* Cuxhaven (8001384)
* Otterndorf (8004738)
* Hamburg-Neugraben (8002553)
* Hamburg-Harburg (8002548)
* Hamburg Hbf (8002549)

### Manueller Testlauf
```bash
# 1. Verspätungsprüfung testen
python3 /root/db-monitor/monitor.py delays

# 2. Baustellenprüfung testen
python3 /root/db-monitor/monitor.py construction
```

---

## 7. Phase 5: Zeitgesteuerte Cronjobs (Hermes Scheduler)

Zur Ausführung ohne Token-Kosten (`--no-agent`) werden Wrapper in `~/.hermes/scripts/` hinterlegt:

```bash
mkdir -p ~/.hermes/scripts

# Delays-Wrapper anlegen
cat << 'EOF' > ~/.hermes/scripts/check_delays.py
import subprocess, sys
res = subprocess.run([sys.executable, "/root/db-monitor/monitor.py", "delays"], capture_output=True, text=True)
if res.stdout.strip() and "Keine neuen Verspätungen" not in res.stdout:
    print(res.stdout.strip())
EOF

# Baustellen-Wrapper anlegen
cat << 'EOF' > ~/.hermes/scripts/check_construction.py
import subprocess, sys
res = subprocess.run([sys.executable, "/root/db-monitor/monitor.py", "construction"], capture_output=True, text=True)
if res.stdout.strip() and "Keine neuen Baustellenmeldungen" not in res.stdout:
    print(res.stdout.strip())
EOF

chmod +x ~/.hermes/scripts/*.py
```

### Geplante Aufgaben registrieren
```bash
# 1. Früh-Check vor dem Berufsverkehr (04:00 Uhr)
hermes cron create "0 4 * * *" \
  --name "db-delay-morning" \
  --script "check_delays.py" \
  --no-agent \
  --deliver discord

# 2. Feierabendverkehr alle 30 Minuten (15:00 bis 17:00 Uhr)
hermes cron create "0,30 15-17 * * *" \
  --name "db-delay-rushhour" \
  --script "check_delays.py" \
  --no-agent \
  --deliver discord

# 3. Baustellen-Scan zweimal täglich (04:05 und 15:05 Uhr)
hermes cron create "5 4,15 * * *" \
  --name "db-baustellen" \
  --script "check_construction.py" \
  --no-agent \
  --deliver discord
```

Mit `hermes cron list` lässt sich der aktive Zeitplan jederzeit prüfen.

---

## 8. Phase 6: Dauerbetrieb als systemd-Dienst

Datei `/etc/systemd/system/hermes.service`:
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

Dienst aktivieren und starten:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now hermes
sudo systemctl status hermes
```

---

## 9. Nützliche Troubleshooting-Befehle

| Zweck | Befehl |
|---|---|
| Gateway-Status prüfen | `hermes gateway status` |
| Live-Logs anzeigen | `journalctl -u hermes -f` |
| Cronjobs anzeigen | `hermes cron list` |
| Einzelnen Job manuell auslösen | `hermes cron run <JOB_NAME_ODER_ID>` |
| Systemressourcen prüfen | `htop` bzw. `free -m` |