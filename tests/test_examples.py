"""Verifiziert: example_all.json — jedes Beispiel parst und produziert ein Garmin-Dict."""

import json
from pathlib import Path

from json_to_garmin import Workout, to_garmin_dict

EXAMPLE = Path(__file__).parent.parent / "example_all.json"


def test_examples_parse_and_serialize():
    raw = json.loads(EXAMPLE.read_text())
    assert "workouts" in raw and len(raw["workouts"]) > 0

    for w_raw in raw["workouts"]:
        # _label / _comment Felder filtern
        clean = {k: v for k, v in w_raw.items() if not k.startswith("_")}
        w = Workout.model_validate(clean)
        d = to_garmin_dict(w)
        assert d["workoutName"] == w.name
        assert d["sportType"]["sportTypeKey"] in {
            "running", "cycling", "swimming", "fitness_equipment"
        }
        assert len(d["workoutSegments"][0]["workoutSteps"]) >= 1
