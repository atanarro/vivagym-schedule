#!/usr/bin/env python3
"""Scrape the VivaGym Paseo de las Delicias class timetable and emit an .ics file."""
import hashlib
import re
import sys
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

URL = "https://www.vivagym.com/es-es/gimnasios/madrid/capital/paseo-de-las-delicias/activity-calendar/"
GYM_NAME = "VivaGym Paseo de las Delicias"
GYM_ADDRESS = "Paseo de las Delicias, Madrid"
OUT_PATH = "schedule.ics"

# Fixed Monday anchor (2024-01-01). Only the weekday matters: RRULE repeats weekly forever.
ANCHOR_MONDAY = datetime(2024, 1, 1)

DAY_ORDER = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
DAY_TO_OFFSET = {d: i for i, d in enumerate(DAY_ORDER)}
DAY_TO_ICAL = {
    "Lunes": "MO", "Martes": "TU", "Miércoles": "WE", "Jueves": "TH",
    "Viernes": "FR", "Sábado": "SA", "Domingo": "SU",
}
ROOM_NAMES = {"E1": "Estudio 1", "E2": "Estudio 2", "SOF": "Sala Fitness", "OUT": "Exterior / Madrid Río"}

ENTRY_RE = re.compile(r"^(.*?)\s+(E1|E2|SOF|OUT)\s+(\d+)'$")


def fetch_events():
    resp = requests.get(URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if table is None:
        raise RuntimeError("No <table> found on the page - site layout may have changed")

    rows = table.find_all("tr")
    header_cells = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
    days = header_cells[1:]  # skip "Inicio"
    if days != DAY_ORDER:
        raise RuntimeError(f"Unexpected day headers: {days!r} - site layout may have changed")

    events = []
    for row in rows[1:]:
        cells = row.find_all(["th", "td"])
        if not cells:
            continue
        time_s = cells[0].get_text(strip=True)
        for d, cell in zip(days, cells[1:]):
            text = re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()
            if not text:
                continue
            m = ENTRY_RE.match(text)
            if not m:
                raise RuntimeError(f"Could not parse cell text: {text!r}")
            name, code, duration = m.group(1).strip(), m.group(2), int(m.group(3))
            events.append((time_s, d, name, code, duration))
    return events


def ics_escape(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")


def stable_uid(day, time_s, name, code):
    key = f"{day}|{time_s}|{name}|{code}".encode("utf-8")
    return hashlib.sha1(key).hexdigest() + "@vivagym-schedule.local"


def build_ics(events):
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//VivaGym Schedule Scraper//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{GYM_NAME} - Clases",
        "X-WR-TIMEZONE:Europe/Madrid",
    ]

    for time_s, day, name, code, duration in events:
        offset = DAY_TO_OFFSET[day]
        date = ANCHOR_MONDAY + timedelta(days=offset)
        hour, minute = (int(x) for x in time_s.split(":"))
        start_dt = date.replace(hour=hour, minute=minute)
        end_dt = start_dt + timedelta(minutes=duration)
        room = ROOM_NAMES.get(code, code)
        uid = stable_uid(day, time_s, name, code)

        description = "\\n".join(
            ics_escape(part) for part in (
                f"Clase dirigida: {name}",
                f"Duración: {duration} min",
                f"Sala: {room}",
                f"{GYM_NAME}, {GYM_ADDRESS}",
            )
        )

        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_stamp}",
            f"DTSTART;TZID=Europe/Madrid:{start_dt.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND;TZID=Europe/Madrid:{end_dt.strftime('%Y%m%dT%H%M%S')}",
            f"RRULE:FREQ=WEEKLY;BYDAY={DAY_TO_ICAL[day]}",
            f"SUMMARY:{ics_escape(name)}",
            f"LOCATION:{ics_escape(f'{room}, {GYM_NAME}')}",
            f"DESCRIPTION:{description}",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main():
    events = fetch_events()
    if not events:
        print("No events parsed - aborting without touching the output file", file=sys.stderr)
        sys.exit(1)
    ics_content = build_ics(events)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(ics_content)
    print(f"Wrote {OUT_PATH} with {len(events)} recurring events")


if __name__ == "__main__":
    main()
