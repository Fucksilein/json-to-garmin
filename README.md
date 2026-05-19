# json-to-garmin

Generic JSON-defined workouts, uploaded to Garmin Connect.

Sport-agnostic (run / bike / swim / strength), arbitrarily nested repeats, targets as power, HR zone, pace, cadence, or speed. Author your training in plain JSON (with a JSON Schema for editor autocomplete), validate it with Pydantic, push it to your Garmin Connect calendar.

---

> ## ⚠️ Disclaimer
>
> This is an **unofficial, community-maintained** tool. It is **not affiliated with, endorsed by, or sponsored by Garmin Ltd.** or its subsidiaries. "Garmin" and "Garmin Connect" are trademarks of Garmin Ltd., used here nominatively to describe the target service.
>
> The tool relies on the unofficial [`garminconnect`](https://github.com/cyberjunky/python-garminconnect) library, which calls private (undocumented) Garmin Connect endpoints. **Automated access to Garmin Connect may violate Garmin's Terms of Service.** Use at your own risk — including the risk of account suspension, IP blocking, or the API breaking without notice.
>
> The software is provided "AS IS", without warranty of any kind. The authors accept no liability for any damage resulting from use of this software. See [LICENSE](LICENSE).

---

## Status

Pre-1.0. Validated end-to-end against live Garmin Connect on 2026-05-09 with all 8 example workouts in [`example_all.json`](example_all.json).

API stability is not guaranteed: Garmin can change their endpoints at any time. If something breaks, open an issue or run the live roundtrip script to re-validate.

## Features

- **Sport-agnostic model** — bike, run, swim, strength, other
- **Nested repeats** — repeats inside repeats inside repeats, as deep as you want
- **All Garmin target types** — absolute power (W), power zone, HR zone, pace (min/km), cadence, speed
- **End conditions** — time, distance, lap-button, calories
- **Strict validation** — Pydantic v2 with `extra="forbid"`; typos in JSON fail loudly
- **JSON Schema** ([`schema.json`](schema.json)) — autocomplete and inline validation in any editor that understands JSON Schema (VS Code, JetBrains, etc.)
- **Convenience builders** — Python helpers for common workout patterns (`build_run_intervals`, `build_run_threshold`, `build_bike_intervals`, `build_bike_zone`, …)
- **Live roundtrip script** — upload the example library, inspect in Garmin Connect, clean up

## Install

Requires Python 3.12+.

```bash
pip install git+https://github.com/Fucksilein/json-to-garmin.git
```

Or, if you use [Poetry](https://python-poetry.org/):

```toml
[tool.poetry.dependencies]
json-to-garmin = { git = "https://github.com/Fucksilein/json-to-garmin.git" }
```

## Quick start

1. **Author a workout JSON** — e.g. `minimal_example.json`:

    ```json
    {
      "$schema": "./schema.json",
      "_comment": "Minimal example",
      "workouts": [
        {
          "_label": "Bike: Cadence drill (90-100 rpm)",
          "name": "Bike Cadence Drill",
          "sport": "bike",
          "steps": [
            {
              "type": "step",
              "kind": "work",
              "end": "time",
              "value": 1800,
              "target": { "kind": "cadence", "low": 90, "high": 100 }
            }
          ]
        },
        {
          "_label": "Swim: lap-button (manual, no end condition)",
          "name": "Swim 45min Easy",
          "sport": "swim",
          "steps": [
            { "type": "step", "kind": "work", "end": "lap_button", "value": null, "note": "Easy, lap button" }
          ]
        },
        {
          "_label": "Strength: time-based, no target",
          "name": "Gym 30min",
          "sport": "strength",
          "steps": [
            { "type": "step", "kind": "work", "end": "time", "value": 1800 }
          ]
        }
      ]
    }
    ```

2. **Validate & inspect** the Garmin API payload (no network):

    ```bash
    json-to-garmin minimal_example.json --dryrun
    ```

3. **Upload + schedule** (single workout):

    ```bash
    export GARMIN_EMAIL=you@example.com
    export GARMIN_PASSWORD=...
    json-to-garmin minimal_example.json --date 2026-05-15
    ```

The wrapper supports `_label` / `_comment` keys (ignored at parse) plus a `workouts` array. A bare workout object (no wrapper) is also accepted.

### Upload a training week

Plan whole training weeks in one file with explicit per-day dates. Sessions without a `workout` are rest days and skipped on upload.

```json
{
  "$schema": "./schema.json",
  "sessions": [
    { "date": "2026-05-18", "workout": { "name": "Easy Run", "sport": "run", "steps": [/* ... */] } },
    { "date": "2026-05-19" },
    { "date": "2026-05-20", "workout": { "name": "Bike Z3", "sport": "bike", "steps": [/* ... */] } }
  ]
}
```

```bash
upload-week week.json --dryrun                # print API dicts, no login
upload-week week.json --date 2026-05-20       # upload only this one session
upload-week week.json                         # upload the whole week (best-effort)
```

Upload errors mid-week are logged and counted; the command continues and exits non-zero if anything failed. See [`example_week.json`](example_week.json) for a full 7-day reference.

### Python API

If you want programmatic access instead of the CLI, all public symbols are exported:

```python
from garminconnect import Garmin
from json_to_garmin import Workout, upload_and_schedule

workout = Workout.model_validate_json(raw_json_string)

client = Garmin("you@example.com", "secret")
client.login()
result = upload_and_schedule(workout, "2026-05-15", client=client)
# {"workout_id": 12345, "scheduled_workout_id": 67890, "raw": {...}}

# or — print the Garmin API payload without hitting the wire:
upload_and_schedule(workout, dry_run=True)
```

### Using the builders

```python
from json_to_garmin import build_run_intervals, to_garmin_dict

w = build_run_intervals(
    name="5x1km @ 4:30",
    reps=5,
    interval_dist_m=1000,
    interval_pace="4:30",
    interval_pace_window=10,   # ±10 s window
    recovery_dist_m=1000,
    recovery_hr_zone=2,
    warmup_min=10,
    cooldown_min=10,
)

api_dict = to_garmin_dict(w)
```

## Data model

```
Workout
├── name, sport, description?, estimated_duration_sec?, estimated_distance_m?
└── steps: list[Step | Repeat]
            ├── Step
            │   ├── kind:   warmup | work | recover | rest | cooldown | other
            │   ├── end:    time | distance | lap_button | calories
            │   ├── value:  seconds / meters / kcal (None for lap_button)
            │   ├── target: Target
            │   └── note?
            └── Repeat
                ├── iterations
                ├── skip_last_rest (default true)
                └── steps: list[Step | Repeat]   ← recursive
```

### Target kinds

| `kind`        | Fields                                   | Notes                                        |
|---------------|------------------------------------------|----------------------------------------------|
| `none`        | —                                        | No target                                    |
| `power`       | `low`, `high` (watts, absolute)          | E.g. `low: 246, high: 266`                   |
| `power_zone`  | `zone` (1–7)                             | Resolved against athlete profile by Garmin   |
| `hr_zone`     | `zone` (1–5)                             | Resolved against athlete profile by Garmin   |
| `pace`        | `pace_low`, `pace_high` as `"M:SS"` /km  | `low` = faster (smaller min/km)              |
| `cadence`     | `low`, `high` (rpm or spm)               |                                              |
| `speed`       | `low`, `high` (m/s)                      |                                              |

### JSON Schema

Reference [`schema.json`](schema.json) at the top of your workout files for autocomplete + inline validation in your editor. The schema accepts **both** top-level layouts the CLI understands:

- **Bare workout** — a single `Workout` object:

    ```json
    {
      "$schema": "./schema.json",
      "name": "...",
      "sport": "run",
      "steps": [...]
    }
    ```

- **Wrapper** — `{ "$schema"?, "_comment"?, "workouts": [Workout, ...] }`, where each entry may also carry an optional `_label` doc string. This is what [`example_all.json`](example_all.json) uses.

- **Week wrapper** — `{ "$schema"?, "_comment"?, "sessions": [{ "date": "YYYY-MM-DD", "workout"?: {...} }, ...] }` for the `upload-week` command. Sessions without a `workout` are rest days. See [`example_week.json`](example_week.json).

Regenerate after model changes:

```bash
poetry run python scripts/regenerate_schema.py
```

## Convenience builders

All return a `Workout`; pair with `to_garmin_dict()` or `upload_and_schedule()`.

| Builder                 | What it makes                                         |
|-------------------------|-------------------------------------------------------|
| `build_run_intervals`   | Warmup + N × (interval w/ pace target + recovery) + cooldown |
| `build_run_threshold`   | Warmup + N × (interval w/ explicit pace low/high + recovery) + cooldown |
| `build_bike_intervals`  | Warmup + N × (work + rest) + optional GA1 fill block + cooldown; supports absolute watts or power-zone mode |
| `build_run_easy`        | Easy run with WU/CD in HR zone 1 (configurable, `wu_min=0` disables) |
| `build_bike_easy`       | Single time-based work step in a power range          |
| `build_bike_zone`       | Easy bike with WU/CD in power zone 1 and work in a chosen power zone (FTP-portable) |
| `build_swim`            | Easy swim with WU/CD, no target (`wu_min=0` disables) |
| `build_gym`             | Single time-based strength step                       |

## Live roundtrip test

`scripts/live_garmin_roundtrip.py` uploads all 8 example workouts, schedules them across the next 7 days, pauses for manual inspection, then deletes them.

```bash
export GARMIN_EMAIL=you@example.com
export GARMIN_PASSWORD=...

poetry run python scripts/live_garmin_roundtrip.py            # full flow
poetry run python scripts/live_garmin_roundtrip.py --dry-run  # no login, just print dicts
poetry run python scripts/live_garmin_roundtrip.py --keep     # skip cleanup prompt
poetry run python scripts/live_garmin_roundtrip.py --cleanup-only  # tear down a previous run
```

State (workout IDs needed for cleanup) is persisted to `scripts/.live_test_state.json` (gitignored). The token cache lives at `~/.garminconnect`. First login may prompt for an MFA code.

## Garmin behavior — observations from real uploads

These are documented quirks confirmed against live Garmin Connect on 2026-05-09. Worth knowing before authoring workouts:

- **Zones are resolved per-athlete.** `power_zone: 3` displays as "Power Zone 3 (215–266 W)" for the account that owns the workout. Means: zone-based workouts are portable across athletes without code changes. Absolute targets (`power: low/high`) appear as-given.
- **Pace is shown as km/h in Garmin Connect**, not min/km. `pace_low: "4:20"`, `pace_high: "4:40"` displays as "13.8–12.9 km/h". `low` is the faster value (higher km/h).
- **Lap-button steps** appear as "Press lap button / Duration". The optional `note` is shown verbatim. No `value` needed.
- **Unschedule before delete.** Garmin may reject deleting a workout that's still on the calendar. `delete_uploaded()` enforces the order automatically. The library distinguishes `workoutId` (template) from `scheduledWorkoutId` (calendar entry); the upload-and-schedule flow returns both.
- **Return shape of `upload_and_schedule()`**: `{"workout_id": int, "scheduled_workout_id": int | None, "raw": <upload-response>}`.

## Limitations / non-goals

- One-way: this is JSON → Garmin. There is no reverse sync (Garmin → JSON), no .FIT export, no activity/result fetching.
- API stability is not guaranteed. The underlying `garminconnect` library targets undocumented endpoints; Garmin can break it without warning.
- No retries, no rate-limiting, no caching. If you upload many workouts in a tight loop you may get throttled or blocked.

## Development

```bash
poetry install
poetry run pytest                     # 29 tests
poetry run python scripts/regenerate_schema.py
poetry build                          # wheel + sdist in dist/
```

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgments

Built on top of:

- **[`garminconnect`](https://github.com/cyberjunky/python-garminconnect)** by Ron Klinkien (MIT) — the unofficial Python wrapper around Garmin Connect that does the heavy lifting.
- **[Pydantic](https://docs.pydantic.dev/)** v2 — validation and JSON Schema generation.

## Trademark notice

"Garmin" and "Garmin Connect" are trademarks or registered trademarks of Garmin Ltd. or its subsidiaries. All other trademarks are the property of their respective owners. This project is not affiliated with, endorsed by, sponsored by, or otherwise associated with Garmin Ltd.
