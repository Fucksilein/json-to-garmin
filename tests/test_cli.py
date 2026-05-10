"""CLI-Smoke-Tests — kein Garmin-Login, nur Parsing + Dry-Run-Pfad."""

import json
from pathlib import Path

from json_to_garmin.cli import _parse_workouts, main

EXAMPLE = Path(__file__).parent.parent / "example_all.json"


def test_parse_wrapper_format(tmp_path):
    """Der `{"workouts": [...]}`-Wrapper inkl. _label/_comment muss alle Workouts liefern."""
    workouts = _parse_workouts(EXAMPLE)
    raw = json.loads(EXAMPLE.read_text())
    assert len(workouts) == len(raw["workouts"])


def test_parse_single_workout(tmp_path):
    """Bare Workout-Objekt (ohne Wrapper) wird auch akzeptiert."""
    f = tmp_path / "single.json"
    f.write_text(
        json.dumps(
            {
                "name": "Single",
                "sport": "run",
                "steps": [{"type": "step", "kind": "work", "end": "time", "value": 60}],
            }
        )
    )
    workouts = _parse_workouts(f)
    assert len(workouts) == 1
    assert workouts[0].name == "Single"


def test_dryrun_exits_zero(capsys):
    """`--dryrun` darf nicht ins Netz und muss exit 0 liefern."""
    rc = main([str(EXAMPLE), "--dryrun"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "workout(s)" in out
    assert "workoutName" in out  # API-Dict wurde gedumpt
