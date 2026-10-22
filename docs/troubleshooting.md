# Fehleranalyse & Diagnose / Troubleshooting & Incident Analysis

| 🇩🇪 Deutsch | 🇬🇧 English |
| :--- | :--- |
| **Über dieses Dokument**<br>Dieses Dokument fasst alle Hürden, Fehlermeldungen und Lösungswege zusammen, die während des Aufbaus und Betriebs des Systems aufgetreten sind. Es dient als Nachschlagewerk bei Problemen mit Schnittstellen, Ratenbegrenzungen, Zeitzonen oder Hintergrunddiensten. | **About This Document**<br>This document summarizes all hurdles, runtime errors, and architectural remediations encountered during setup and operation. It serves as a permanent reference for issues with APIs, rate limits, timezones, or background services. |

---

## 1. Grenzen von `bahn.expert` & Umstellung / Limitations of `bahn.expert` & Dual-Source Migration

| 🇩🇪 Deutsch | 🇬🇧 English |
| :--- | :--- |
| **Symptom 1: Veraltete Daten & Snapshots**<br>Bei interaktiven Anfragen im Discord-Kanal antwortete der Assistent:<br>*„Ich kann dir für 14:00 Uhr keine konkreten Abfahrten nennen. Die Daten reichen nur bis etwa 10:00 Uhr heute Vormittag.“*<br><br>**Ursache:**<br>`bahn.expert` ist eine moderne Single-Page-Application (SPA). Bei Direktaufrufen liefert die Seite oft nur einen begrenzten Snapshot oder gecachte Daten. Da KI-Scraper keine interaktiven Buttons („später laden“) anklicken können, schloss das Modell fälschlicherweise, dass keine weiteren Daten vorliegen. | **Symptom 1: Stale Snapshots & Caching**<br>When queried in Discord, the bot replied:<br>*"I cannot provide concrete departures for 14:00. Retrieved data only reaches up to approximately 10:00 this morning."*<br><br>**Root Cause:**<br>`bahn.expert` operates as a Single-Page Application (SPA). Direct GET requests often return limited DOM snapshots or cached morning data. Because automated AI scrapers cannot interactively click UI elements ("load later"), the model concluded that no further schedules existed. |
| **Symptom 2: HTTP 404 bei REST-Endpunkten**<br>Aufrufe wie `https://bahn.expert/api/iris/v2/abfahrten/<StationID>` schlugen mit `HTTP 404 Not Found` fehl. Die Pfade sind öffentlich nicht als stabile REST-Endpunkte erreichbar. | **Symptom 2: HTTP 404 on REST Endpoints**<br>Scraping attempts targeting `https://bahn.expert/api/iris/v2/abfahrten/<StationID>` yielded `HTTP 404 Not Found`. These internal paths are not maintained as stable public REST endpoints. |
| **Die Lösung: Kombi-Strategie**<br>Aufteilung in zwei spezialisierte Quellen:<br>1. **Live-Lage & Gleise:** Offizielle DB IRIS-Web-Bahnhofstafeln (`iris.noncd.db.de`) ohne JavaScript-Overhead via DS100-Kürzel (`AH`, `AHAR`, `ABX`, `AST`, `ACX`).<br>2. **Verbindungssuche & Fahrten:** `delaybahn.com` mit expliziten URL-Parametern (`date`, `time`, `window`). | **The Solution: Dual-Source Strategy**<br>Division into two dedicated upstream sources:<br>1. **Live Status & Tracks:** Official DB IRIS station departure boards (`iris.noncd.db.de`) without JavaScript overhead via DS100 codes (`AH`, `AHAR`, `ABX`, `AST`, `ACX`).<br>2. **Route Queries:** `delaybahn.com` with explicit URL query parameters (`date`, `time`, `window`). |

---

## 2. Empfehlung: Open-Source-Projekt `delay_bahn` /Recommendation: The Open-Source Project `delay_bahn` 

| 🇩🇪 Deutsch | 🇬🇧 English |
| :--- | :--- |
| **Projekt-Würdigung & Empfehlung**<br>Für strukturierte Verbindungsabfragen und Fahrplananalysen empfehlen wir das Open-Source-Projekt:<br>👉 **Repository:** [https://github.com/sha2nkt/delay_bahn](https://github.com/sha2nkt/delay_bahn) *(Entwickler: `sha2nkt`)*<br><br>**Warum delay_bahn?**<br>Die Web-App wurde ebenfalls mit Unterstützung von KI entwickelt und basiert auf einer hervorragenden Idee: Sie bereitet rohe HAFAS-Fahrplandaten über einfache URL-Parameter (`fromId`, `toId`, `date`, `time`, `window`) auf. Dadurch entfällt das fehleranfällige Ausfüllen komplexer Webformulare, was ideal für autonome KI-Agenten ist.<br><br>**Wichtige Guardrail:** Statistische 7-Tage-Durchschnittswerte aus Delaybahn dürfen niemals als akute Verspätung des heutigen Tages gemeldet werden. | **Project Attribution & Recommendation**<br>For structured route queries and delay analytics, we strongly recommend the open-source project:<br>👉 **Repository:** [https://github.com/sha2nkt/delay_bahn](https://github.com/sha2nkt/delay_bahn) *(Creator: `sha2nkt`)*<br><br>**Why delay_bahn?**<br>The application was also built with AI assistance and implements an outstanding concept: exposing raw HAFAS transit data through straightforward URL parameters (`fromId`, `toId`, `date`, `time`, `window`). This eliminates the need for interactive form filling, making it exceptionally reliable for automated AI agent parsing.<br><br>**Critical Guardrail:** Historical 7-day average metrics from Delaybahn must never be presented as today's actual live delay. |

---

## 3. API Tokens, Rate Limits & Config Adjustments / API-Tokens & `config.yaml`

| 🇩🇪 Deutsch | 🇬🇧 English |
| :--- | :--- |
| **HTTP 429: Rate-Limit bei OpenRouter**<br>Wenn Cronjobs und interaktive Abfragen dicht aufeinander folgten, wurde das Minutenlimit (Requests/Tokens per Minute) bei OpenRouter kurzzeitig überschritten.<br><br>**HTTP 404: Veraltete Modell-ID**<br>Der Eintrag `anthropic/claude-3.5-haiku` schlug fehl mit: *„no provider serves this model anymore“*.<br><br>**Lösung in `~/.hermes/config.yaml`:**<br>Festlegung des Cron-Modells auf die aktive Modell-ID `anthropic/claude-haiku-5.5` und Aktivierung von `catch_up_missed`. | **HTTP 429: Rate Limiting on OpenRouter**<br>When scheduled cron jobs coincided with interactive chat requests, OpenRouter's rate limits (requests/tokens per minute) were temporarily exceeded.<br><br>**HTTP 404: Deprecated Model ID**<br>Referencing `anthropic/claude-3.5-haiku` failed with: *"no provider serves this model anymore"*/<br><br>**Resolution in `~/.hermes/config.yaml`:**<br>Explicitly pinning the cron engine to the active model ID `anthropic/claude-haiku-5.5` and enabling `catch_up_missed`. |

```yaml
# ~/.hermes/config.yaml
cron:
  catch_up_missed: true
  model: anthropic/claude-haiku-5.5
  model_provider: openrouter
```

---

## 4. Multi-Profile Gateway & Session Handling / Gateway & Sitzungsverwaltung

| 🇩🇪 Deutsch | 🇬🇧 English |
| :--- | :--- |
| **Gateway Double-Binding (Zwei getrennte Prozesse)**<br>Hermes erlaubt pro Host nur **ein einziges Gateway**. Der Versuch, zwei getrennte Systemd-Dienste (`hermes` und `hermes-navigator`) zu starten, führte zu Socket-Kollisionen und wiederholten `SIGTERM`-Crashes.<br><br>**Lösung:**<br>Migration auf Multiplexing (`hermes gateway migrate --multiplex`), wodurch beide Profile (`default` und `navigator`) von einem einzigen Dienst mit dem Flag `--replace` verwaltet werden. | **Gateway Double-Binding (Two Independent Processes)**<br>Hermes permits only **one host gateway instance**. Attempting to run two independent systemd services (`hermes` and `hermes-navigator`) caused socket collisions and cyclic `SIGTERM` crashes.<br><br>**Resolution:**<br>Migrate both profiles to multiplexing via `hermes gateway migrate --multiplex`, allowing a single background daemon executing `--replace` to manage both profiles. |
| **HTTP 400: Encrypted Reasoning Tokens**<br>Fehlermeldung: *„Your request contains encrypted reasoning or compaction content from multiple providers. No single provider can decrypt the mixed history.“*<br><br>**Ursache:**<br>Wurde zuvor ein Reasoning-Modell genutzt, befinden sich verschlüsselte Denkketten in der SQLite-Sitzungshistorie (`~/.hermes/state.db`), die andere Modelle nicht lesen können.<br><br>**Lösung:**<br>Im Chat `/new` aufrufen oder auf dem VPS die Sitzungscaches leeren:<br>`rm -rf ~/.hermes/sessions/*` | **HTTP 400: Encrypted Reasoning Tokens**<br>Error message: *"Your request contains encrypted reasoning or compaction content from multiple providers. No single provider can decrypt the mixed history."*<br><br>**Root Cause:**<br>When switching models, encrypted chain-of-thought metadata from previous providers remained stored in SQLite session storage (`~/.hermes/state.db`), which subsequent models cannot parse.<br><br>**Resolution:**<br>Execute `/new` in Discord or purge session caches directly on the host VPS:<br>`rm -rf ~/.hermes/sessions/*` |

---

## 5. Zeitzonen-Versatz bei Cronjobs / Timezone Offsets in Scheduler 

| 🇩🇪 Deutsch | 🇬🇧 English |
| :--- | :--- |
| **Zeitzonen-Prüfung: CEST-Lokalzeit vs. UTC-Scheduler**<br>Auf diesem VPS-Setup operiert Hermes bereits nativ in deutscher Lokalzeit (**CEST / `+02:00`**), wodurch Ausdrücke wie `30 4 * * *` (04:30 Uhr) oder `0,30 15,16,17 * * *` (15:00–17:30 Uhr) direkt zur gewünschten Ortszeit ausgeführt werden.<br><br>⚠️ **Wichtiger Prüfpunkt für andere Setups:**<br>Viele Standard-Linux-Server und Hermes-Instanzen operieren standardmäßig in **UTC (`+00:00`)**. Vor dem Einrichten von Cronjobs sollte mit `hermes cron list` immer der Zeitstempel unter `Next run` geprüft werden:<br>• Endet der Zeitstempel auf `+02:00` (Sommerzeit) bzw. `+01:00` (Winterzeit), greift die deutsche Lokalzeit direkt.<br>• Endet er auf `+00:00` (UTC), müssen die Cron-Stunden um den Versatz zurückgerechnet werden (z. B. 04:30 dt. Zeit = `30 2 * * *` UTC), da Aufträge sonst 1 bis 2 Stunden zu spät starten. | **Timezone Verification: CEST Local Time vs. UTC Scheduler**<br>On this VPS setup, Hermes runs natively in German local time (**CEST / `+02:00`**), allowing cron schedules such as `30 4 * * *` (04:30 AM) or `0,30 15,16,17 * * *` (15:00–17:30) to trigger directly at the intended local hour.<br><br>⚠️ **Crucial Check for Other Environments:**<br>Many standard Linux server deployments and default Hermes installations operate in **UTC (`+00:00`)**. Always verify the active timezone by checking the `Next run` timestamp in `hermes cron list` before defining tasks:<br>• If timestamps end with `+02:00` (CEST) or `+01:00` (CET), local German time expressions execute as written.<br>• If timestamps end with `+00:00` (UTC), the hour expressions must be offset accordingly (e.g., 04:30 local German time = `30 2 * * *` UTC); otherwise, commuter checks will trigger 1 to 2 hours late. |

---

## 6. Quick Diagnostic Commands / Schnelle Diagnose-Befehle

| 🇩🇪 Zweck | 🇬🇧 Objective | Befehl / Command |
| :--- | :--- | :--- |
| Gateway- und Profilstatus prüfen | Inspect gateway and profile status | `hermes gateway status` |
| Live-Logs des Hintergrunddienstes | Follow live systemd service logs | `journalctl -u hermes -f` |
| Registrierte Cronjobs auflisten | List all scheduled cron tasks | `hermes cron list` |
| Job sofort manuell testen | Manually trigger a scheduled job | `hermes cron run agent-rushhour-check` |
| Dienst nach Prompt-/YAML-Änderung neu laden | Reload daemon after config changes | `hermes gateway restart` |
| Systemressourcen & Speicher prüfen | Inspect VPS memory and CPU usage | `htop` oder `free -m` |