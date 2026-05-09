# CLAUDE.md — json-to-garmin

Generisches JSON-Workout-Modell + Adapter zu Garmin Connect. Sport-agnostisch (Bike/Run/Swim/Strength), beliebig verschachtelte Repeats, Targets als Power/HR-Zone/Pace/Cadence/Speed.

## Status

Vorerst privat, lokal eingebunden via Pfad-Dependency. Kein PyPI, kein GitHub-Remote.

## Repo-Layout

```
json-to-garmin/
├── pyproject.toml
├── schema.json                     ← aus model.Workout generiert
├── example_all.json                ← Referenzbeispiele (alle Features)
├── src/json_to_garmin/
│   ├── __init__.py                 ← Re-Exports
│   ├── model.py                    ← Workout, Step, Repeat, Target
│   ├── garmin_api.py               ← to_garmin_dict, upload_and_schedule
│   └── builders.py                 ← Convenience-Konstruktoren
└── tests/
    ├── test_model.py               ← Pydantic-Validierung, JSON-Roundtrip
    ├── test_garmin_api.py          ← API-IDs, Step-Reihenfolge, Repeat-Übersetzung
    ├── test_builders.py            ← Builder-Output-Struktur
    └── test_examples.py            ← example_all.json parst + serialisiert
```


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
