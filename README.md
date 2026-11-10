# vivagym-schedule

Weekly-recurring calendar feeds of the class timetable for VivaGym Paseo de
las Delicias (Madrid), scraped from the
[official activity calendar page](https://www.vivagym.com/es-es/gimnasios/madrid/capital/paseo-de-las-delicias/activity-calendar/),
with a feed per class type so you can subscribe only to what you care about.

**Browse all feeds:** https://atanarro.github.io/vivagym-schedule/

## Feeds

All feeds live under `docs/` and are listed machine-readably in
[`docs/index.json`](docs/index.json). There's no server, so "filtering" is
static: pick the pre-generated file for the class type you want, or combine
several by subscribing your calendar app to more than one feed at once.

| Feed | URL |
|---|---|
| All classes | `docs/schedule.ics` |
| One class type | `docs/schedule-<slug>.ics`, e.g. `schedule-pilates.ics`, `schedule-virtual-cycling.ics` |

Current class types (see `docs/index.json` for the live, authoritative list
with per-type class counts): Cycling, Dance, Fit Moves, GAP, Pilates, Run Club
(Madrid Río), V-Cross, V-Fight, V-Power, Virtual Cycling.

## Subscribe to a feed

Use the **GitHub Pages** URL as a calendar **subscription** (not a one-time
import), so your calendar app re-fetches it automatically:

```
webcal://atanarro.github.io/vivagym-schedule/schedule.ics
webcal://atanarro.github.io/vivagym-schedule/schedule-pilates.ics
```

- **Google Calendar**: Settings → Add calendar → From URL → paste the `https://` version of the link.
- **Apple Calendar**: File → New Calendar Subscription → paste the `webcal://` link.
- **Outlook**: Add calendar → Subscribe from web → paste the `https://` version.

> ⚠️ Don't use `raw.githubusercontent.com` links. That host serves every
> file as `text/plain` with `x-content-type-options: nosniff`, which tells
> clients not to guess the real type — several calendar apps then refuse to
> parse it as a calendar (you'd see zero events, or a text download instead
> of a subscription). GitHub Pages serves the same files as `text/calendar`,
> which works correctly.

Calendar apps typically re-poll a subscribed URL every 12–24 hours, so
changes may take up to a day to show up even after this repo updates.

## How it stays up to date

A [GitHub Action](.github/workflows/update-schedule.yml) runs every Monday
at 05:00 UTC (06:00 Madrid time in winter / 07:00 in summer — cron doesn't
follow DST), re-scrapes the page, regenerates everything under `docs/`, and
commits if anything changed. You can also trigger it manually from the
Actions tab ("Run workflow").

Each class keeps a stable UID across runs (hashed from day + time + class
name + room code), so re-scraping updates existing events instead of
duplicating them.

## Running it locally

```
pip install -r requirements.txt
python3 scraper.py
```

## Caveats

- This is static pre-filtering, not a real API: there's no way to combine
  filters ad hoc (e.g. "Pilates OR Dance on Tuesdays") beyond subscribing to
  multiple feeds. A dynamic query API (`?type=...&day=...`) would need an
  actual server (e.g. a Cloudflare Worker) — ask if you want that instead.
- The schedule is anchored to a fixed Monday (2024-01-01) purely so the
  weekday lines up; `RRULE:FREQ=WEEKLY` repeats it forever.
- If VivaGym changes the page's HTML structure, the scraper will fail loudly
  (it raises instead of silently writing a wrong/empty calendar) — check the
  Action's logs.
- This covers only the Paseo de las Delicias club's directed classes
  (clases dirigidas), not Virtual/on-demand content or other clubs.
