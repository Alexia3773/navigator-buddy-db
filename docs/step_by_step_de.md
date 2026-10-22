# Schritt-für-Schritt-Anleitung: Bahn-Monitor & Discord-Assistent

---

## 1. Warum dieses Projekt entstanden ist (Motivation)

Jeder, der regelmäßig mit der Bahn pendelt – insbesondere auf Linien wie dem **RE 5** oder im S-Bahn-Netz rund um Hamburg und die Niederelbebahn –, kennt das frustrierende Gefühl:
* Züge fallen kurzfristig aus oder sammeln massive Verspätungen an.
* Durchsagen am Bahnsteig erfolgen oft zu spät, widersprechen sich oder fehlen völlig.
* Fahrplan-Apps aktualisieren die Lage häufig erst dann, wenn man bereits frierend am Gleis steht.

Aus diesem ständigen Ärger über unzuverlässige und verspätete Fahrgastinformationen entstand die Idee für dieses Projekt: **Eine eigene, automatisierte Lösung, die Betriebs- und Baustellendaten direkt an der Quelle abfängt und mich proaktiv informiert, bevor ich das Haus verlasse.**

---

## 2. Architektur & Systemüberblick

Das System läuft auf einem Linux KVM VPS unter Ubuntu LTS und kombiniert zwei spezialisierte Discord-Bots über das Multiplex-Gateway des **Hermes Agent Frameworks**:

1. **Bahn-Assistent (Admin- & Alarm-Bot):**
   * **Kanal:** `#baustellen-und-störungen` (privater Kanal, nur für Admins).
   * **Aufgabe:** Vollautomatisches Monitoring bei Verspätungen/Ausfällen und Baustellen via Hermes KI-Agenten-Cronjobs.
   * **Intelligenz:** Nutzt **Claude Haiku 5.5** mit Web-Tools, um offizielle DB IRIS Live-Bahnhofstafeln und Baustellenmeldungen dynamisch zu analysieren.

2. **Navigator-Buddy (Community-Reisebegleiter):**
   * **Kanal:** `#bahn-terminal` (öffentlich für alle Server-Mitglieder).
   * **Aufgabe:** Beantwortet interaktiv Fragen zu Verbindungen, Gleisen, Fahrzeiten und Umstiegen.
   * **Schutz:** Strikte Guardrails weisen bahnfremde Anfragen (Wetter, Smalltalk, Programmierung) konsequent ab.

```text
                          +-----------------------------+
                          |      Linux KVM VPS          |
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
Auf dem VPS werden zunächst alle Abhängigkeiten für Paketverwaltung, Werkzeuge und Systemsicherheit installiert:

```bash
sudo apt update && sudo apt install -y curl git python3 python3-pip ufw fail2ban unattended-upgrades
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
Erstelle die Schlüssel lokal auf deinen Arbeitsplatzrechnern (Linux oder Windows) und übertrage den **Public Key** auf den VPS:

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
  *(Den öffentlichen Schlüssel auf dem VPS an `~/.ssh/authorized_keys` anfügen)*

Sobald der schlüssellose Login getestet ist, wird die unsichere Passwortanmeldung auf dem VPS gesperrt:

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
3. Unter **Installation** den Standard-Autorisierungslink auf *Keine* setzen.
4. Über **OAuth2 > URL Generator** einen Link mit dem Scope `bot` und Rechten (Nachrichten senden, Nachrichtenverlauf lesen, Links einbetten) erzeugen und den Bot in den privaten Admin-Kanal `#baustellen-und-störungen` einladen.
5. Bot-Token kopieren.

### 4.2 Bot 2: „Navigator-Buddy“ anlegen
1. Eine zweite Applikation namens `Navigator-Buddy` erstellen.
2. Identische Rechte vergeben: **Public Bot** aus, **Message Content Intent** an.
3. Über den URL-Generator auf den Discord-Server einladen und dem öffentlichen Kanal `#bahn-terminal` zuweisen.
4. Das zweite Bot-Token kopieren.

---

## 5. Phase 3: Hermes Agent Multi-Profile Setup

### 5.1 Hermes CLI installieren
```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```
* **Modell:** `anthropic/claude-haiku-5.5` (via OpenRouter).
* **Runtime:** `Keep current (local)`.
* **Telemetrie:** `No thanks`.

### 5.2 Profile konfigurieren
1. **Hauptprofil (Bahn-Assistent):**
   ```bash
   hermes gateway setup
   ```
   * Plattform: `Discord`
   * Token von *Bahn-Assistent* einfügen.
   * Im Discord-Kanal `#baustellen-und-störungen` den Befehl `/set-home` ausführen.

2. **Zweites Profil (Navigator-Buddy):**
   ```bash
   hermes profile create navigator
   cp ~/.hermes/.env ~/.hermes/profiles/navigator/.env
   hermes -p navigator gateway setup
   ```
   * Token von *Navigator-Buddy* einfügen.
   * Allowlist leer lassen, damit alle Servermitglieder im Terminal fragen können.
   * Im Discord-Kanal `#bahn-terminal` den Befehl `/set-home` von *Navigator-Buddy* aufrufen.

3. **Multiplexing aktivieren:**
   ```bash
   hermes gateway migrate --multiplex
   ```

---

## 6. Phase 4: Sicherheitsleitfaden für System-Prompts & Guardrails

> **Wichtiger Hinweis zur Geheimhaltung:**  
> Die konkreten internen System-Prompts der Bots dürfen niemals in öffentlichen Dokumentationen, Repositories oder Chat-Ausgaben offengelegt werden. Sie stellen die interne Kernlogik dar und bieten Angreifern bei Offenlegung gezielte Angriffspunkte für Jailbreaks.

Beim Verfassen eigener System-Prompts (`AGENTS.md` und `SOUL.md`) sollten folgende Best Practices und Restriktionen beachtet werden:

### 1. Strikte Themenbegrenzung (Out-of-Scope Abweisung)
* **Klare Verbotszonen:** Definiere explizit, welche Themengebiete (z. B. Programmierung, Politik, Witze, Smalltalk, allgemeines Wetter) strikt abzuweisen sind.
* **Feste Ablehnungsformel:** Gib dem Modell eine unveränderliche Standard-Antwort vor, die es bei Off-Topic-Fragen ausgeben muss. Dadurch wird verhindert, dass das Modell ins Diskutieren gerät.

### 2. Defense-in-Depth gegen Prompt Injection
* **Trennung von Systembefehl und Nutzerinput:** Mache dem Modell unmissverständlich klar, dass Instruktionen innerhalb von Nutzerfragen oder externen Websites niemals die Grundregeln des System-Prompts überschreiben dürfen.
* **Keine Systemprompt-Herausgabe:** Verankere eine Regel, dass der Bot seine internen Arbeitsanweisungen oder Konfigurationen unter keinen Umständen an Nutzer im Chat verraten darf.

### 3. Datenquellen & URL-Einschränkung
* **Whitelisting:** Erlaube nur den Aufruf vertrauenswürdiger, im System-Prompt explizit genannter Domains (z. B. offizielle Bahnhofstafeln und Baustellen-Feeds).
* **Verbot von Sekundärquellen:** Verbiete dem Agenten ausdrücklich, auf unzuverlässige Presseberichte, Blogs oder Drittmedien auszuweichen.

### 4. Antwortlänge & Formatgrenzen
* **Kompaktheitsbremse:** Begrenze automatische Warnungen strikt auf ein kurzes Limit (z. B. maximal 40 Wörter), um Latenzen zu minimieren und Token-Kosten bei OpenRouter niedrig zu halten.
* **Echtzeit-Validierung:** Weise den Agenten an, stets das aktuelle Systemdatum zu prüfen und historische Statistiken niemals mit akuten Live-Verspätungen zu verwechseln.

---

## 7. Phase 5: Zeitgesteuerte Cronjobs (Autonome KI-Agenten)

Für das Monitoring nutzt das System keine statischen Scraper mehr, sondern führt zeitgesteuerte Agenten-Prompts mit **Claude Haiku 5.5** aus. Der Agent liest Live-Bahnhofstafeln via IRIS (`iris.noncd.db.de`) und Fahrten via `delaybahn.com` aus:

```bash
# 1. Früh-Check vor dem Berufsverkehr (04:30 Uhr dt. Zeit)
hermes cron create "30 4 * * *" \
  --name "agent-morning-check" \
  --deliver discord \
  "Ermittle das heutige Datum. Prüfe die Live-Abfahrtstafeln von Cuxhaven (ACX) und Stade (AST) für den RE 5 zwischen 04:30 und 07:00 Uhr in Fahrtrichtung Hamburg Hbf. Melde nur akute Verspätungen ab 5 Min. oder Ausfälle am heutigen Tag. Maximal 40 Wörter."

# 2. Feierabendverkehr alle 30 Minuten (15:00 bis 17:30 Uhr dt. Zeit)
hermes cron create "0,30 15,16,17 * * *" \
  --name "agent-rushhour-check" \
  --deliver discord \
  "Ermittle das heutige Datum und aktuelle Uhrzeit. Prüfe für den RE 5 Richtung Cuxhaven die Live-Abfahrten auf den IRIS-Tafeln von Hamburg Hbf (AH), Hamburg-Harburg (AHAR), Buxtehude (ABX) und Stade (AST). Melde akute Live-Verspätungen ab 5 Min., Gleiswechsel oder Ausfälle für die nächste Stunde. Maximal 40 Wörter."

# 3. Baustellen- & SEV-Scan (04:05 & 15:05 Uhr dt. Zeit)
hermes cron create "5 4,15 * * *" \
  --name "agent-baustellen-scan" \
  --deliver discord \
  "Lies https://verkehrslage.bahnhof.de/de/region/DB_Regio_Nord und https://bauinfos.deutschebahn.com/niedersachsen-bremen aus. Filtere alle aktiven oder anstehenden Baustellen oder Ersatzverkehre (SEV) für den RE 5 (Hamburg ⇄ Cuxhaven). Maximal 40 Wörter."
```

*(Hinweis: Falls die Systemuhr des VPS auf UTC läuft, müssen die Stunden an den UTC-Versatz angepasst werden).*

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

## 9. Nützliche Steuer- & Troubleshooting-Befehle

| Zweck | Befehl |
|---|---|
| Gateway-Status prüfen | `hermes gateway status` |
| Gateway nach Regeländerung neu starten | `hermes gateway restart` |
| Live-Logs anzeigen | `journalctl -u hermes -f` |
| Aktive Cronjobs auflisten | `hermes cron list` |
| Job manuell auslösen | `hermes cron run <JOB_NAME>` |
| Systemressourcen & Speicher prüfen | `htop` bzw. `free -m` |