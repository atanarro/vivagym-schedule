#!/usr/bin/env python3
"""Scrape the VivaGym Paseo de las Delicias class timetable and emit .ics feeds.

Writes, under docs/ (served via GitHub Pages / raw.githubusercontent.com):
  - schedule.ics              all classes
  - schedule-<type-slug>.ics  one feed per class type (Pilates, Cycling, ...)
  - index.json                machine-readable list of available feeds
  - index.html                human-browsable page linking to each feed
"""
import hashlib
import html
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

URL = "https://www.vivagym.com/es-es/gimnasios/madrid/capital/paseo-de-las-delicias/activity-calendar/"
GYM_NAME = "VivaGym Paseo de las Delicias"
GYM_ADDRESS = "Paseo de las Delicias, Madrid"
OUT_DIR = "docs"
# GitHub Pages (serves docs/ at the repo root) sets the correct
# "text/calendar" Content-Type; raw.githubusercontent.com serves everything
# as "text/plain" with x-content-type-options: nosniff, which some calendar
# clients refuse to parse as a calendar feed at all.
PAGES_BASE = "https://atanarro.github.io/vivagym-schedule"

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


def slugify(name):
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug


def ics_escape(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")


def stable_uid(day, time_s, name, code):
    key = f"{day}|{time_s}|{name}|{code}".encode("utf-8")
    return hashlib.sha1(key).hexdigest() + "@vivagym-schedule.local"


VTIMEZONE_MADRID = [
    "BEGIN:VTIMEZONE",
    "TZID:Europe/Madrid",
    "X-LIC-LOCATION:Europe/Madrid",
    "BEGIN:DAYLIGHT",
    "TZOFFSETFROM:+0100",
    "TZOFFSETTO:+0200",
    "TZNAME:CEST",
    "DTSTART:19700329T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
    "END:DAYLIGHT",
    "BEGIN:STANDARD",
    "TZOFFSETFROM:+0200",
    "TZOFFSETTO:+0100",
    "TZNAME:CET",
    "DTSTART:19701025T030000",
    "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
    "END:STANDARD",
    "END:VTIMEZONE",
]


def fold_line(line):
    """RFC 5545 line folding: split at 75 octets, continuation lines start with a space."""
    data = line.encode("utf-8")
    if len(data) <= 75:
        return [line]
    chunks = []
    start = 0
    limit = 75
    while start < len(data):
        end = min(start + limit, len(data))
        # don't split a multi-byte UTF-8 sequence
        while end < len(data) and (data[end] & 0xC0) == 0x80:
            end -= 1
        chunks.append(data[start:end].decode("utf-8"))
        start = end
        limit = 74  # continuation lines lose 1 octet to the leading space
    return [chunks[0]] + [" " + c for c in chunks[1:]]


def build_ics(events, calname_suffix=""):
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//VivaGym Schedule Scraper//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{GYM_NAME} - Clases{calname_suffix}",
        "X-WR-TIMEZONE:Europe/Madrid",
        *VTIMEZONE_MADRID,
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
    folded = [folded_line for line in lines for folded_line in fold_line(line)]
    return "\r\n".join(folded) + "\r\n"


def build_index_html(feeds):
    rows = "\n".join(
        f'<li><strong>{html.escape(f["name"])}</strong> '
        f'<span class="count">({f["count"]} clases/semana)</span><br>'
        f'<a href="webcal://{PAGES_BASE.split("://", 1)[1]}/{f["file"]}">webcal://</a> · '
        f'<a href="{PAGES_BASE}/{f["file"]}">https://</a></li>'
        for f in feeds
    )
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VivaGym Paseo de las Delicias - Horarios</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 640px; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }}
  li {{ margin-bottom: 1rem; }}
  .count {{ color: #666; font-size: 0.9em; }}
  code {{ background: #f0f0f0; padding: 0.1em 0.3em; border-radius: 3px; }}
</style>
</head>
<body>
<h1>VivaGym Paseo de las Delicias - Horarios</h1>
<p>Feeds de calendario (.ics) generados semanalmente a partir del
<a href="{URL}">horario oficial</a>. Suscríbete (no los importes una sola vez)
para que se actualicen solos.</p>
<h2>Todas las clases</h2>
<ul>
<li><a href="webcal://{PAGES_BASE.split("://", 1)[1]}/schedule.ics">webcal://</a> ·
<a href="{PAGES_BASE}/schedule.ics">https://</a></li>
</ul>
<h2>Por tipo de clase</h2>
<ul>
{rows}
</ul>
</body>
</html>
"""


def main():
    events = fetch_events()
    if not events:
        print("No events parsed - aborting without touching output files", file=sys.stderr)
        sys.exit(1)

    os.makedirs(OUT_DIR, exist_ok=True)

    # Full feed
    with open(os.path.join(OUT_DIR, "schedule.ics"), "w", encoding="utf-8") as f:
        f.write(build_ics(events))

    # Per-type feeds
    by_type = defaultdict(list)
    for ev in events:
        by_type[ev[2]].append(ev)

    feeds = []
    for name in sorted(by_type):
        type_events = by_type[name]
        slug = slugify(name)
        filename = f"schedule-{slug}.ics"
        with open(os.path.join(OUT_DIR, filename), "w", encoding="utf-8") as f:
            f.write(build_ics(type_events, calname_suffix=f" - {name}"))
        feeds.append({"name": name, "slug": slug, "file": filename, "count": len(type_events)})

    with open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "base_url": PAGES_BASE,
                "note": "Use base_url (GitHub Pages), not raw.githubusercontent.com: "
                        "the latter serves text/plain and some calendar clients "
                        "won't parse it as a calendar feed.",
                "all": {"file": "schedule.ics", "count": len(events)},
                "by_type": feeds,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_index_html(feeds))

    print(f"Wrote {len(feeds) + 3} files to {OUT_DIR}/ ({len(events)} total events, {len(feeds)} class types)")


if __name__ == "__main__":
    main()
