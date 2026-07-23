#!/usr/bin/env python3
"""
Trägt rückwirkend Transfers ab dem 04.07.2026 nach (Start der neuen Saison
war der 01.07., die ersten paar Tage waren unruhig/nicht aussagekräftig).

Geht dafür durch JEDEN Spieler im aktuellen Kader-Snapshot (kader_latest.json)
und schaut in dessen Profil ("Bisherige Stationen"), ob der aktuelle Stint
(die letzte Zeile mit einem Ab-Datum in der Vergangenheit oder heute) ab dem
04.07.2026 begonnen hat. Falls ja, wird daraus ein Transfer-Eintrag gebaut
und in data.json eingetragen (dedupliziert wie bei den anderen Skripten).

Das sind ~400+ Spieler insgesamt - viel zu viele für einen Lauf. Deshalb
merkt sich das Skript in history_progress.json, welche Spieler-IDs schon
geprüft wurden, und bearbeitet pro Lauf nur eine begrenzte Anzahl (BATCH_SIZE).
Bei 4 Läufen/Tag und BATCH_SIZE=15 sind alle Spieler nach ca. 5-6 Tagen durch.
"""

import json
import os
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(__file__)
CLUBS_FILE = os.path.join(BASE_DIR, "clubs.json")
KADER_LATEST_FILE = os.path.join(BASE_DIR, "kader_latest.json")
DATA_FILE = os.path.join(BASE_DIR, "data.json")
PROGRESS_FILE = os.path.join(BASE_DIR, "history_progress.json")

CUTOFF_DATE = datetime(2026, 7, 4)  # nur Transfers ab diesem Datum zählen
BATCH_SIZE = 15

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_player_stations(session: requests.Session, player_id: str):
    """Liefert die Liste der Stationen (club_id, ab_date, bis_date, is_loan)
    aus der Tabelle "Bisherige Stationen" des Spielerprofils, chronologisch."""
    try:
        resp = session.get(
            f"https://www.anstoss-online.de/?do=spieler&spieler_id={player_id}",
            timeout=15,
        )
        resp.raise_for_status()
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException:
        return None  # None = Fehler, nicht "keine Stationen"

    keywords = {"verein", "ab", "bis", "einsätze", "leihe"}
    table = None
    for t in soup.find_all("table"):
        header_cells = t.find_all(["th", "td"], limit=10)
        header_text = " ".join(c.get_text(strip=True).lower() for c in header_cells)
        if sum(1 for kw in keywords if kw in header_text) >= 3:
            table = t
            break
    if table is None:
        return []

    stations = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 6:
            continue
        club_link = cells[0].find("a", href=re.compile(r"do=verein"))
        if not club_link:
            continue
        club_id_m = re.search(r"verein_id=(\d+)", club_link.get("href", ""))
        club_id = club_id_m.group(1) if club_id_m else None
        club_name = club_link.get_text(strip=True)
        ab_date = cells[1].get_text(strip=True)
        leihe_text = cells[5].get_text(strip=True)
        stations.append({
            "club_id": club_id,
            "club_name": club_name,
            "ab_date": ab_date,
            "is_loan": bool(leihe_text),
        })
    return stations


def parse_date(s):
    try:
        return datetime.strptime(s, "%d.%m.%Y")
    except (ValueError, TypeError):
        return None


def main() -> int:
    clubs = load_json(CLUBS_FILE, [])
    club_names_by_id = {c["id"]: c["name"] for c in clubs}

    kader_latest = load_json(KADER_LATEST_FILE, {"clubs": {}})
    squads = kader_latest.get("clubs", {})

    # Alle Spieler-IDs im aktuellen Kader sammeln, mit Info aus dem Snapshot
    all_players = {}  # player_id -> {info..., current_club_id}
    for club_id, squad in squads.items():
        for p in squad:
            all_players[p["player_id"]] = {**p, "current_club_id": club_id}

    progress = load_json(PROGRESS_FILE, {"checked": []})
    checked = set(progress.get("checked", []))

    todo = [pid for pid in all_players if pid not in checked][:BATCH_SIZE]
    print(f"{len(all_players)} Spieler insgesamt, {len(checked)} schon geprüft, "
          f"{len(all_players) - len(checked)} offen. Bearbeite {len(todo)} in diesem Lauf.")

    if not todo:
        print("Nichts mehr zu tun - alle Spieler bereits geprüft.")
        return 0

    session = requests.Session()
    session.headers.update(HEADERS)

    existing = load_json(DATA_FILE, [])
    existing_ids = {t["id"] for t in existing}
    today = datetime.now(timezone.utc).replace(tzinfo=None)

    found_count = 0
    for pid in todo:
        time.sleep(1)
        stations = fetch_player_stations(session, pid)
        if stations is None:
            continue  # Fehler beim Abruf - NICHT als geprüft markieren, später erneut versuchen

        checked.add(pid)  # erfolgreich abgerufen (auch wenn ggf. 0 Stationen) -> als geprüft merken

        # Aktueller Stint = letzte Zeile mit Ab-Datum <= heute
        past_or_today = [s for s in stations if parse_date(s["ab_date"]) and parse_date(s["ab_date"]) <= today]
        if not past_or_today:
            continue
        current = past_or_today[-1]
        current_date = parse_date(current["ab_date"])
        if current_date < CUTOFF_DATE:
            continue  # Transfer liegt vor unserem Stichtag - nicht relevant

        idx = stations.index(current)
        previous = stations[idx - 1] if idx > 0 else None

        info = all_players[pid]
        to_club_id = info["current_club_id"]
        to_club_name = club_names_by_id.get(to_club_id, current["club_name"])
        from_club_id = previous["club_id"] if previous else None
        from_club_name = previous["club_name"] if previous else "außerhalb Nordirland1"

        date_str = current["ab_date"]
        transfer_id = f"{pid}-{from_club_id}-{to_club_id}-{date_str}"
        if transfer_id in existing_ids:
            continue

        existing.append({
            "id": transfer_id,
            "pos": info.get("pos"),
            "player": info.get("player"),
            "player_id": pid,
            "strength": info.get("strength"),
            "age": info.get("age"),
            "nationality": info.get("nationality"),
            "from_club": from_club_name,
            "from_club_id": from_club_id,
            "to_club": to_club_name,
            "to_club_id": to_club_id,
            "date": date_str,
            "is_loan": current["is_loan"],
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "nachgetragen": True,
        })
        existing_ids.add(transfer_id)
        found_count += 1

    def sort_key(t):
        return parse_date(t.get("date")) or datetime.min

    existing.sort(key=sort_key, reverse=True)
    save_json(DATA_FILE, existing)
    save_json(PROGRESS_FILE, {"checked": sorted(checked)})

    print(f"{found_count} nachgetragene Transfers gefunden. "
          f"{len(checked)}/{len(all_players)} Spieler insgesamt geprüft.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
