# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Überblick

Generisches JSON-Workout-Modell + Adapter zu Garmin Connect. Sport-agnostisch (Bike/Run/Swim/Strength), beliebig verschachtelte Repeats, Targets als Power/HR-Zone/Pace/Cadence/Speed.

## Status

Öffentlich auf GitHub (MIT): https://github.com/Fucksilein/json-to-garmin. Kein PyPI-Release.
Installierbar via `pip install git+https://github.com/Fucksilein/json-to-garmin.git`.

## Commands

- Tests: `poetry run pytest`
- Einzelner Test: `poetry run pytest tests/test_garmin_api.py::test_distance_condition_uses_corrected_id`
- Wheel bauen: `poetry build` (Output in `dist/`, nicht committen)
- `schema.json` regenerieren: `poetry run python scripts/regenerate_schema.py`
- Live-Roundtrip gegen Garmin: `poetry run python scripts/live_garmin_roundtrip.py` (siehe unten)

## Pipeline

`Workout` (model.py, generisch) → `to_garmin_dict()` (garmin_api.py) → API-Dict via die Pydantic-Modelle in `garminconnect.workout` (`RunningWorkout`, `CyclingWorkout`, …). `upload_and_schedule()` und `delete_uploaded()` sind die einzigen Touchpoints zur Garmin-API; alles davor ist reine Übersetzung und in Tests ohne Netzwerk verifizierbar (`dry_run=True`). Builder bauen ausschließlich `Workout` — niemals API-Dicts. Die JSON-Diskriminator-Keys `"type": "step"` / `"type": "repeat"` kommen aus dem `Annotated[Union[...], Field(discriminator="type")]` in `model.py`.

## Repo-Layout

```
json-to-garmin/
├── pyproject.toml
├── schema.json                     ← aus model.Workout generiert (scripts/regenerate_schema.py)
├── example_all.json                ← Referenzbeispiele (alle Features)
├── src/json_to_garmin/
│   ├── __init__.py                 ← Re-Exports
│   ├── model.py                    ← Workout, Step, Repeat, Target
│   ├── garmin_api.py               ← to_garmin_dict, upload_and_schedule, delete_uploaded
│   └── builders.py                 ← Convenience-Konstruktoren
├── scripts/
│   ├── regenerate_schema.py        ← schema.json aus model.Workout neu schreiben
│   └── live_garmin_roundtrip.py    ← Upload aller example_all-Workouts → manueller Check → Delete
└── tests/
    ├── test_model.py               ← Pydantic-Validierung, JSON-Roundtrip
    ├── test_garmin_api.py          ← API-IDs, Step-Reihenfolge, Repeat-Übersetzung
    ├── test_builders.py            ← Builder-Output-Struktur
    └── test_examples.py            ← example_all.json parst + serialisiert
```

## Live-Roundtrip-Test

`scripts/live_garmin_roundtrip.py` — kein Pytest-Test (echter Netzwerk-Call), bewusst manuell zu starten.

```
export GARMIN_EMAIL=...
export GARMIN_PASSWORD=...
poetry run python scripts/live_garmin_roundtrip.py            # Upload + Schedule + Pause + Cleanup
poetry run python scripts/live_garmin_roundtrip.py --dry-run  # nur to_garmin_dict, kein Login
poetry run python scripts/live_garmin_roundtrip.py --keep     # nicht aufräumen
poetry run python scripts/live_garmin_roundtrip.py --cleanup-only  # State-Datei abräumen
```

- Lädt alle 8 Beispiele aus `example_all.json` mit Namens-Prefix `[live-test] ` hoch und plant sie auf `heute … heute+6 Tage`.
- IDs werden in `scripts/.live_test_state.json` (gitignored) persistiert. Falls das Skript zwischen Upload und Cleanup abbricht, mit `--cleanup-only` aufräumen.
- Token-Cache: `~/.garminconnect` (oder `GARMINTOKENS` env var). Erstes Login fragt MFA-Code im Terminal.


## Datenmodell

```
Workout
├── name, sport, description?, estimated_duration_sec?, estimated_distance_m?
└── steps: list[Step | Repeat]
            ├── Step
            │   ├── kind:   warmup | work | recover | rest | cooldown | other
            │   ├── end:    time | distance | lap_button | calories
            │   ├── value:  Sekunden / Meter / kcal (None bei lap_button)
            │   ├── target: Target
            │   └── note?
            └── Repeat
                ├── iterations
                ├── skip_last_rest (default true)
                └── steps: list[Step | Repeat]   ← rekursiv
```

`Target.kind` und welche Felder gelten:
- `none` — keine Felder
- `power` — `low`/`high` (Watt absolut)
- `power_zone` — `zone` (1-7)
- `hr_zone` — `zone` (1-5)
- `pace` — `pace_low`/`pace_high` als `"M:SS"` pro km (low = schneller)
- `cadence` — `low`/`high` (rpm/spm)
- `speed` — `low`/`high` (m/s)

## Garmin-API-Korrekturen

`garminconnect`-Library hat einige API-IDs falsch. In `garmin_api.py` korrigiert:

| Feld                        | Library | API (korrekt) |
|-----------------------------|---------|----------------|
| `ConditionType.DISTANCE`    | 1       | **3**          |
| `pace.zone` Target-Type     | —       | **5** (workoutTargetTypeId) |

Power und HR-Zone nutzen die Library-Werte direkt (`POWER=2`, `HEART_RATE=4`), Schlüssel sind `power.zone` bzw. `heart.rate.zone`.

`endConditionValue=None` wird vom Garmin-Pydantic-Modell beim `to_dict()` weggelassen (z. B. bei `lap_button`) — das ist OK.

## Garmin-Verhalten (validiert via Live-Roundtrip)

Beobachtungen aus echten Uploads + Anzeige in Garmin Connect — beim Erweitern beachten, nicht erneut nachprüfen müssen:

- **Zonen werden gegen das Athleten-Profil aufgelöst.** `power_zone: 3` → Garmin zeigt „Leistungsbereich 3 (215-266 W)", `hr_zone: 2` → „Herzfrequenz-Bereich 2 (131-154 bpm)". Konsequenz: zonen-basierte Workouts sind portabel über Athleten ohne Code-Änderung. Absolute Targets (`power: low/high`) erscheinen 1:1.
- **Pace wird in Garmin als km/h angezeigt** (nicht min/km). `pace_low="4:20"`, `pace_high="4:40"` → Anzeige „13,8-12,9 km/h". `low` ist der schnellere Wert (höhere km/h). Die Inversion macht `pace_to_ms()` in `garmin_api.py` — niemals direkt von Sekunden auf m/s mappen ohne diese Funktion.
- **Lap-Button-Steps** zeigen sich als „Lap-Taste drücken / Dauer". Note wird durchgereicht. Kein `endConditionValue` nötig.
- **`unschedule_workout` MUSS vor `delete_workout` laufen.** `delete_uploaded()` erzwingt diese Reihenfolge — Garmin lehnt sonst potentiell ab. `workoutId` (Template) und `scheduledWorkoutId` (Kalender-Eintrag) sind getrennte IDs; beide werden vom Upload+Schedule-Flow zurückgegeben.
- **`upload_and_schedule()` Rückgabe-Schema** ist `{"workout_id": int, "scheduled_workout_id": int | None, "raw": <upload-response>}` — bei Erweiterungen beibehalten, sonst bricht das Live-Skript.

Diese Erkenntnisse stammen aus dem Roundtrip am 2026-05-09 mit allen 8 Beispielen aus `example_all.json`. Falls API-Verhalten sich ändert, neu validieren via `scripts/live_garmin_roundtrip.py`.

## Konventionen

- Code/Identifier: Englisch | Docstrings/Kommentare: Deutsch
- Pydantic v2, `extra="forbid"` auf allen Modellen
- Keine Magic Numbers in `garmin_api.py` — alle korrigierten IDs als Modul-Konstanten
- Builder geben `Workout` zurück, nicht das API-Dict; Übersetzung passiert in `to_garmin_dict()`

## Erweiterung

**Neuer Target-Typ** (z. B. `cadence_zone`):
1. `TargetKind` Literal in `model.py` erweitern
2. Branch in `garmin_api._target_dict()` hinzufügen
3. Test in `tests/test_garmin_api.py`

**Neue End-Condition** (z. B. `heart_rate`):
1. `EndCondition` Literal in `model.py`
2. Branch in `garmin_api._end_condition()`

**Neuer Sport:**
1. `Sport` Literal in `model.py`
2. Mapping in `garmin_api._SPORT_TO_WORKOUT_CLS`

**Neuer Convenience-Builder:** in `builders.py` als reine Funktion, gibt `Workout` zurück.