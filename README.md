# vivagym-schedule

Weekly-recurring calendar feed of the class timetable for VivaGym Paseo de las
Delicias (Madrid), scraped from the
[official activity calendar page](https://www.vivagym.com/es-es/gimnasios/madrid/capital/paseo-de-las-delicias/activity-calendar/).

## Subscribe to the calendar

Use the "raw" GitHub URL for `schedule.ics` as a calendar subscription
(not a one-time import), so your calendar app re-fetches it automatically:

```
webcal://raw.githubusercontent.com/<your-github-username>/vivagym-schedule/main/schedule.ics
```

- **Google Calendar**: Settings → Add calendar → From URL → paste the `https://` version of the link above.
- **Apple Calendar**: File → New Calendar Subscription → paste the `webcal://` link.
- **Outlook**: Add calendar → Subscribe from web → paste the `https://` version.

Calendar apps typically re-poll a subscribed URL every 12–24 hours, so
changes may take up to a day to show up even after this repo updates.

## How it stays up to date

A [GitHub Action](.github/workflows/update-schedule.yml) runs every Monday
at 05:00 UTC (06:00 Madrid time in winter / 07:00 in summer — cron doesn't
follow DST), re-scrapes the page, regenerates `schedule.ics`, and commits it
if anything changed. You can also trigger it manually from the Actions tab
("Run workflow").

Each class keeps a stable UID across runs (hashed from day + time + class
name + room code), so re-scraping updates existing events instead of
duplicating them.

## Running it locally

```
pip install -r requirements.txt
python3 scraper.py
```

## Caveats

- The schedule is anchored to a fixed Monday (2024-01-01) purely so the
  weekday lines up; `RRULE:FREQ=WEEKLY` repeats it forever.
- If VivaGym changes the page's HTML structure, the scraper will fail loudly
  (it raises instead of silently writing a wrong/empty calendar) — check the
  Action's logs.
- This covers only the Paseo de las Delicias club's directed classes
  (clases dirigidas), not Virtual/on-demand content or other clubs.
