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
   * **Aufgabe:** Vollautomatisches Monitoring bei Verspätungen/Ausfällen und Baustellen via Hermes KI-Agenten-Cronjobs.
   * **Intelligenz:** Nutzt **Claude Haiku 5.5** mit Web-Tools, um Live-Daten dynamisch von `bahn.expert`, `verkehrslage.bahnhof.de` und `bauinfos.deutschebahn.com` zu analysieren und für Pendler zusammenzufassen.

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

## 7. Phase 5: Zeitgesteuerte Cronjobs (Autonome KI-Agenten)

Statt starrer statischer Skripte führt Hermes zu den definierten Pendlerzeiten echte **KI-Agenten-Aufgaben mit Claude Haiku 5.5** aus. Der Agent recherchiert mithilfe seiner Web-Tools eigenständig auf `bahn.expert`, `verkehrslage.bahnhof.de` und `bauinfos.deutschebahn.com`, bewertet die Lage nach deinen Kriterien (Verspätungen ab 5 Min., Ausfälle, Gleiswechsel, Baustellen) und sendet strukturierte Kurzberichte direkt nach Discord.

### 7.1 Agenten-Instruktionen hinterlegen (`~/.hermes/AGENTS.md`)
In `~/.hermes/AGENTS.md` sind die Richtlinien und Quellen für den Bahn-Assistenten definiert:
```markdown
# Rolle: Bahn-Assistent
Du bist der spezialisierte Bahn-Monitor für die Pendlerstrecke Hamburg ⇄ Cuxhaven (RE5 / Niederelbebahn) im Discord-Kanal #baustellen-und-störungen.

## Überwachte Bahnhöfe & Streckenabschnitt:
- Hamburg Hbf, Hamburg-Harburg, Hamburg-Neugraben, Buxtehude, Stade, Otterndorf, Cuxhaven.

## Datenquellen & Web-Tools:
- Live-Betriebslage & Störungen: [https://verkehrslage.bahnhof.de](https://verkehrslage.bahnhof.de) sowie [https://bahn.expert](https://bahn.expert) (Abfahrten RE5 / S-Bahn)
- Baustellen, Ersatzverkehr & Fahrplanänderungen: [https://bauinfos.deutschebahn.com](https://bauinfos.deutschebahn.com)

## Verhaltensregeln für Cron-Runs:
1. Nutze deine Web-Tools, um die aktuellen Daten der genannten Quellen abzurufen.
2. Filterung: Berücksichtige nur Störungen, Ausfälle oder Verspätungen ab 5 Minuten sowie anstehende/aktive Baustellen für diese Strecke.
3. Wenn alles pünktlich und störungsfrei ist: Antworte extrem kurz mit "✅ Keine Störungen auf der Strecke Hamburg ⇄ Cuxhaven."
4. Wenn Störungen oder Arbeiten vorliegen: Fasse Zugnummer, betroffenen Abschnitt, Verzögerung/Ausfall und Ursache kurz und übersichtlich mit Bulletpoints zusammen.

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