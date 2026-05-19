"""Verifiziert: example_all.json + example_week.json — jedes Beispiel parst und produziert ein Garmin-Dict."""

import json
from pathlib import Path

from json_to_garmin import Workout, to_garmin_dict

ROOT = Path(__file__).parent.parent
EXAMPLE = ROOT / "example_all.json"
EXAMPLE_WEEK = ROOT / "example_week.json"

VALID_SPORTS = {"running", "cycling", "swimming", "fitness_equipment", "multi_sport"}


def _validate_workout(w_raw: dict) -> None:
    clean = {k: v for k, v in w_raw.items() if not k.startswith(("_", "$"))}
    w = Workout.model_validate(clean)
    d = to_garmin_dict(w)
    assert d["workoutName"] == w.name
    assert d["sportType"]["sportTypeKey"] in VALID_SPORTS
    assert len(d["workoutSegments"][0]["workoutSteps"]) >= 1


def test_examples_parse_and_serialize():
    raw = json.loads(EXAMPLE.read_text())
    assert "workouts" in raw and len(raw["workouts"]) > 0
    for w_raw in raw["workouts"]:
        _validate_workout(w_raw)


def test_example_week_parse_and_serialize():
    raw = json.loads(EXAMPLE_WEEK.read_text())
    assert "sessions" in raw and len(raw["sessions"]) > 0
    workouts_seen = 0
    for s in raw["sessions"]:
        assert "date" in s
        if "workout" in s:
            _validate_workout(s["workout"])
            workouts_seen += 1
    assert workouts_seen > 0, "example_week.json sollte mindestens ein Workout enthalten"
