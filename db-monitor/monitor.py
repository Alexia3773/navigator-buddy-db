"""
Deutsche Bahn Real-Time Delay and Construction Monitor.
Scrapes DB IRIS API for delays/cancellations and DB Bauinfos for construction notices.
Operates with SQLite deduplication to prevent duplicate alerts.
"""

import sys
import json
import hashlib
import sqlite3
import httpx
from bs4 import BeautifulSoup
from datetime import datetime

DB_FILE = "db-monitor/monitor_state.db"

# Official DB Construction Detail URL for Hamburg Hbf <-> Cuxhaven
VERKEHRSLAGE_URL = (
    "https://verkehrslage.bahnhof.de/de/detail/967dd5f3-a465-4546-baa2-0849df485ac3"
    "?f=2!mv785340!mv8nkxrz!1!1!1!0!md!1q2927!br28fy"
)

# Monitored stations (Niederelbebahn RE5 & S-Bahn hubs)
STATIONS = {
    "Hamburg Hbf": "8002549",
    "Hamburg-Harburg": "8002548",
    "Hamburg-Neugraben": "8002553",
    "Otterndorf": "8004738",
    "Cuxhaven": "8001384"
}

def init_db():
    """Initializes local SQLite database for event deduplication."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS seen_events (
            id TEXT PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def is_new_event(event_id: str) -> bool:
    """Checks if an event was already processed. If not, saves it."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM seen_events WHERE id = ?", (event_id,))
    exists = c.fetchone()
    if not exists:
        c.execute("INSERT INTO seen_events (id) VALUES (?)", (event_id,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def check_delays():
    """Queries bahn.expert / IRIS-API for delays >= 5 mins or train cancellations."""
    alerts = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DB-Monitor/1.0"}

    with httpx.Client(timeout=10.0, headers=headers) as client:
        for station_name, eva_id in STATIONS.items():
            url = f"https://bahn.expert/api/iris/v2/abfahrten/{eva_id}"
            try:
                res = client.get(url)
                if res.status_code != 200:
                    continue
                data = res.json()
                departures = data.get("departures", [])

                for dep in departures[:15]:
                    train = dep.get("train", {}).get("name", "Train")
                    destination = dep.get("destination", "Unknown")
                    raw_id = dep.get("rawId", f"{train}_{destination}")
                    cancelled = dep.get("cancelled", False)
                    delay = dep.get("delayDeparture", 0) or 0
                    messages = [m.get("text", "") for m in dep.get("messages", {}).get("qos", [])]

                    if cancelled:
                        event_key = f"cancel_{raw_id}"
                        if is_new_event(event_key):
                            alerts.append(f"❌ **Cancellation:** {train} to {destination} at {station_name} is cancelled!")
                    elif delay >= 5:
                        event_key = f"delay_{raw_id}_{delay}"
                        if is_new_event(event_key):
                            msg_str = f" ({', '.join(messages)})" if messages else ""
                            alerts.append(f"⚠️ **Delay (+{delay} min):** {train} to {destination} at {station_name}{msg_str}")
            except Exception:
                continue

    if alerts:
        print("📢 **Current Rail Service Alerts & Delays:**\n" + "\n".join(alerts))
    else:
        print("No new delays or cancellations on the monitored route.")

def check_construction():
    """Checks official DB verkehrslage and regional RSS feeds for construction works."""
    alerts = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    with httpx.Client(timeout=15.0, headers=headers, follow_redirects=True) as client:
        # 1. Official DB traffic situation SPA/Detail
        try:
            res = client.get(VERKEHRSLAGE_URL)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                for s in soup(["script", "style", "noscript"]):
                    s.extract()
                text_content = " ".join(soup.stripped_strings)

                content_hash = hashlib.md5(text_content.encode("utf-8")).hexdigest()
                event_key = f"db_vl_{content_hash}"

                if is_new_event(event_key):
                    title = soup.title.string.strip() if soup.title and soup.title.string else "DB Verkehrslage: Hamburg Hbf ⇄ Cuxhaven"
                    alerts.append(
                        f"🚧 **Official DB Rail Notice Update:**\n"
                        f"**Route:** Hamburg Hbf ⇄ Cuxhaven\n"
                        f"**Notice:** {title}\n"
                        f"🔗 [View full report on bahnhof.de]({VERKEHRSLAGE_URL})\n"
                    )
        except Exception:
            pass

        # 2. Regional RSS Feeds (Lower Saxony / Hamburg)
        feed_urls = [
            "https://bauinfos.deutschebahn.com/docs/bahn-baustellen-niedersachsen-bremen.xml",
            "https://bauinfos.deutschebahn.com/docs/bahn-baustellen-hamburg-schleswig-holstein.xml"
        ]
        for url in feed_urls:
            try:
                res = client.get(url)
                if res.status_code != 200:
                    continue
                soup = BeautifulSoup(res.text, "xml")
                for item in soup.find_all("item")[:10]:
                    guid = item.find("guid").text if item.find("guid") else item.find("title").text
                    title = item.find("title").text if item.find("title") else "Construction Notice"
                    desc = item.find("description").text if item.find("description") else ""
                    keywords = ["cuxhaven", "otterndorf", "harburg", "hamburg", "neugraben", "re5", "stade"]
                    content_lower = f"{title} {desc}".lower()
                    if any(k in content_lower for k in keywords):
                        if is_new_event(f"bau_{guid}"):
                            clean_desc = desc[:250] + "..." if len(desc) > 250 else desc
                            alerts.append(f"🚧 **Construction Notice:** {title}\n_{clean_desc}_\n")
            except Exception:
                continue

    if alerts:
        print("📋 **Construction & Traffic Work Notices:**\n" + "\n".join(alerts))
    else:
        print("No new construction notices found.")

if __name__ == "__main__":
    init_db()
    mode = sys.argv[1] if len(sys.argv) > 1 else "delays"
    if mode == "construction":
        check_construction()
    else:
        check_delays()
