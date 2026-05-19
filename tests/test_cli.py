"""CLI-Smoke-Tests — kein Garmin-Login, nur Parsing + Dry-Run-Pfad."""

import json
from pathlib import Path

import pytest

from json_to_garmin.cli import (
    _parse_sessions,
    _parse_workouts,
    main,
    upload_week_main,
)

EXAMPLE = Path(__file__).parent.parent / "example_all.json"
EXAMPLE_WEEK = Path(__file__).parent.parent / "example_week.json"


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


def test_parse_strips_schema_ref(tmp_path):
    """`$schema`-Editor-Hint darf Pydantics `extra=forbid` nicht triggern."""
    f = tmp_path / "with_schema.json"
    f.write_text(
        json.dumps(
            {
                "$schema": "./schema.json",
                "name": "WithSchema",
                "sport": "run",
                "steps": [{"type": "step", "kind": "work", "end": "time", "value": 60}],
            }
        )
    )
    workouts = _parse_workouts(f)
    assert len(workouts) == 1
    assert workouts[0].name == "WithSchema"


def test_dryrun_exits_zero(capsys):
    """`--dryrun` darf nicht ins Netz und muss exit 0 liefern."""
    rc = main([str(EXAMPLE), "--dryrun"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "workout(s)" in out
    assert "workoutName" in out  # API-Dict wurde gedumpt


# --- upload-week ---


def _write_week(tmp_path: Path, sessions: list[dict]) -> Path:
    f = tmp_path / "week.json"
    f.write_text(json.dumps({"sessions": sessions}))
    return f


def test_upload_week_parse_skips_rest_days(tmp_path):
    """Sessions ohne `workout` haben `workout is None` (Ruhetag)."""
    f = _write_week(
        tmp_path,
        [
            {
                "date": "2026-05-18",
                "workout": {
                    "name": "Run",
                    "sport": "run",
                    "steps": [{"type": "step", "kind": "work", "end": "time", "value": 60}],
                },
            },
            {"date": "2026-05-19"},
        ],
    )
    sessions = _parse_sessions(f)
    assert len(sessions) == 2
    assert sessions[0].workout is not None and sessions[0].workout.name == "Run"
    assert sessions[1].workout is None


def test_upload_week_dryrun_prints_dicts(capsys):
    """`upload-week --dryrun` dumped Workout-Dicts, ignoriert Ruhetage."""
    rc = upload_week_main([str(EXAMPLE_WEEK), "--dryrun"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "session(s)" in out and "Ruhetag" in out
    assert "workoutName" in out  # mindestens ein Workout-Dict


def test_upload_week_filter_date(tmp_path, capsys):
    """--date filtert auf eine Session; Workout-Dict wird gedumpt."""
    f = _write_week(
        tmp_path,
        [
            {
                "date": "2026-05-18",
                "workout": {
                    "name": "Run",
                    "sport": "run",
                    "steps": [{"type": "step", "kind": "work", "end": "time", "value": 60}],
                },
            },
            {
                "date": "2026-05-19",
                "workout": {
                    "name": "Bike",
                    "sport": "bike",
                    "steps": [{"type": "step", "kind": "work", "end": "time", "value": 60}],
                },
            },
        ],
    )
    rc = upload_week_main([str(f), "--date", "2026-05-19", "--dryrun"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 session(s)" in out
    assert "Bike" in out and "Run" not in out.split("--- ")[1]  # nur Bike-Block


def test_upload_week_filter_date_unknown(tmp_path):
    """--date ohne Treffer → klarer SystemExit."""
    f = _write_week(tmp_path, [{"date": "2026-05-18"}])
    with pytest.raises(SystemExit, match="2099-01-01"):
        upload_week_main([str(f), "--date", "2099-01-01", "--dryrun"])


def test_upload_week_filter_date_invalid_format(tmp_path):
    """--date mit falschem Format → klarer SystemExit."""
    f = _write_week(tmp_path, [{"date": "2026-05-18"}])
    with pytest.raises(SystemExit, match="YYYY-MM-DD"):
        upload_week_main([str(f), "--date", "18.05.2026", "--dryrun"])


def test_upload_week_meta_keys_filtered(tmp_path, capsys):
    """`_label` und `$schema` brechen Pydantics `extra=forbid` nicht."""
    f = tmp_path / "week.json"
    f.write_text(
        json.dumps(
            {
                "$schema": "./schema.json",
                "_comment": "Woche XY",
                "sessions": [
                    {
                        "date": "2026-05-18",
                        "_label": "Mo",
                        "workout": {
                            "$schema": "./schema.json",
                            "name": "Run",
                            "sport": "run",
                            "steps": [{"type": "step", "kind": "work", "end": "time", "value": 60}],
                        },
                    }
                ],
            }
        )
    )
    rc = upload_week_main([str(f), "--dryrun"])
    assert rc == 0


def test_upload_week_missing_sessions_key(tmp_path):
    """Wrapper-Format mit `workouts` → klarer Fehler, der auf json-to-garmin verweist."""
    f = tmp_path / "wrong.json"
    f.write_text(json.dumps({"workouts": []}))
    with pytest.raises(ValueError, match="sessions"):
        _parse_sessions(f)


def test_upload_week_invalid_date_in_session(tmp_path):
    """Falsches Date-Format in einer Session → klarer ValueError."""
    f = _write_week(tmp_path, [{"date": "18.05.2026"}])
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        _parse_sessions(f)


def test_upload_week_only_rest_days(tmp_path, capsys):
    """Nur Ruhetage → exit 0, kein Login, klare Botschaft."""
    f = _write_week(tmp_path, [{"date": "2026-05-18"}, {"date": "2026-05-19"}])
    rc = upload_week_main([str(f)])  # ohne --dryrun, aber ohne Workouts kein Login
    assert rc == 0
    out = capsys.readouterr().out
    assert "Nichts zu tun" in out
