"""CLI-Entry-Points — JSON-Workouts validieren / hochladen / planen.

Usage:
    json-to-garmin <file.json> --dryrun
    json-to-garmin <file.json> --date YYYY-MM-DD   # benötigt GARMIN_EMAIL/PASSWORD
    upload-week    <file.json> [--dryrun] [--date YYYY-MM-DD]

`json-to-garmin` akzeptiert Wrapper- (`{"workouts": [...]}`) oder Bare-Workout-Format.
`upload-week` akzeptiert `{"sessions": [{"date": "YYYY-MM-DD", "workout"?: {...}}, ...]}`;
Sessions ohne `workout` sind Ruhetage und werden übersprungen.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from json_to_garmin.garmin_api import to_garmin_dict, upload_and_schedule
from json_to_garmin.model import Workout

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _strip_meta(item: dict) -> dict:
    """Editor-Meta-Keys (`_label`, `_comment`, `$schema`, …) wegfiltern.

    Pydantic-Modelle haben `extra="forbid"`, würden also bei einem direkten
    `$schema`-Feld brechen. Wird beim Workout- und beim Session-Parsing genutzt.
    """
    return {k: v for k, v in item.items() if not k.startswith(("_", "$"))}


def _parse_workouts(path: Path) -> list[Workout]:
    """Lädt JSON. Akzeptiert Wrapper-Format `{"workouts": [...]}` oder ein einzelnes Workout."""
    raw = json.loads(path.read_text())
    if isinstance(raw, dict) and "workouts" in raw:
        items = raw["workouts"]
    else:
        items = [raw]
    return [Workout.model_validate(_strip_meta(item)) for item in items]


@dataclass(frozen=True)
class Session:
    date: str
    workout: Workout | None


def _parse_sessions(path: Path) -> list[Session]:
    """Lädt einen Wochenplan: `{"sessions": [{"date": ..., "workout"?: {...}}, ...]}`.

    Sessions ohne `workout`-Key sind Ruhetage → `Session.workout is None`.
    `_label`/`_comment` an Session-Ebene sowie `$schema`/`_comment` am Top-Level werden ignoriert.
    """
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict) or "sessions" not in raw:
        raise ValueError(
            "Erwartet Top-Level-Key 'sessions'. Für Wrapper-/Bare-Workouts: "
            "stattdessen `json-to-garmin` verwenden."
        )

    out: list[Session] = []
    for idx, item in enumerate(raw["sessions"]):
        if not isinstance(item, dict):
            raise ValueError(f"sessions[{idx}]: erwartet Objekt, bekommen {type(item).__name__}.")
        date = item.get("date")
        if not isinstance(date, str) or not _DATE_RE.match(date):
            raise ValueError(
                f"sessions[{idx}].date fehlt oder hat falsches Format "
                f"(erwartet 'YYYY-MM-DD', bekommen {date!r})."
            )
        workout_raw = item.get("workout")
        if workout_raw is None:
            out.append(Session(date=date, workout=None))
        else:
            workout = Workout.model_validate(_strip_meta(workout_raw))
            out.append(Session(date=date, workout=workout))
    return out


def _make_client():
    from garminconnect import Garmin

    email = os.environ.get("GARMIN_EMAIL") or os.environ.get("GARMIN_USER")
    password = os.environ.get("GARMIN_PASSWORD")
    if not email or not password:
        sys.exit("FEHLER: GARMIN_EMAIL und GARMIN_PASSWORD müssen gesetzt sein.")
    tokenstore = os.environ.get("GARMINTOKENS") or str(Path.home() / ".garminconnect")
    client = Garmin(email, password, prompt_mfa=lambda: input("Garmin MFA-Code: "))
    client.login(tokenstore=tokenstore)
    return client


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="json-to-garmin",
        description="Generic JSON workout schema → Garmin Connect.",
    )
    p.add_argument("file", type=Path, help="path to workout JSON")
    p.add_argument(
        "--dryrun",
        "--dry-run",
        action="store_true",
        help="no upload, only print API dict",
    )
    p.add_argument("--date", help="YYYY-MM-DD; schedule single workout on this date")
    args = p.parse_args(argv)

    if not args.file.exists():
        sys.exit(f"FEHLER: Datei nicht gefunden: {args.file}")

    workouts = _parse_workouts(args.file)
    print(f"{len(workouts)} workout(s) from {args.file}")

    if args.dryrun:
        for w in workouts:
            print(f"\n--- {w.name} ({w.sport}) ---")
            print(json.dumps(to_garmin_dict(w), indent=2, ensure_ascii=False))
        return 0

    if args.date and len(workouts) > 1:
        sys.exit("FEHLER: --date funktioniert nur mit genau einem Workout.")

    client = _make_client()
    for w in workouts:
        upload_and_schedule(w, args.date, client=client)
    return 0


def upload_week_main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="upload-week",
        description="Lädt einen Wochenplan (sessions[]) bei Garmin Connect hoch und plant ihn.",
    )
    p.add_argument("file", type=Path, help="Pfad zur Wochenplan-JSON")
    p.add_argument(
        "--dryrun",
        "--dry-run",
        action="store_true",
        help="kein Upload, nur Workout-Dicts ausgeben",
    )
    p.add_argument("--date", help="YYYY-MM-DD; nur diese eine Session hochladen")
    args = p.parse_args(argv)

    if not args.file.exists():
        sys.exit(f"FEHLER: Datei nicht gefunden: {args.file}")
    if args.date and not _DATE_RE.match(args.date):
        sys.exit(f"FEHLER: --date erwartet 'YYYY-MM-DD', bekommen {args.date!r}.")

    sessions = _parse_sessions(args.file)
    if args.date:
        sessions = [s for s in sessions if s.date == args.date]
        if not sessions:
            sys.exit(f"FEHLER: keine Session mit date={args.date}.")

    workout_sessions = [s for s in sessions if s.workout is not None]
    rest_days = len(sessions) - len(workout_sessions)
    print(
        f"{len(sessions)} session(s), {len(workout_sessions)} mit workout, "
        f"{rest_days} Ruhetag(e) from {args.file}"
    )

    if args.dryrun:
        for s in workout_sessions:
            print(f"\n--- {s.date} {s.workout.name} ({s.workout.sport}) ---")
            print(json.dumps(to_garmin_dict(s.workout), indent=2, ensure_ascii=False))
        return 0

    if not workout_sessions:
        print("Nichts zu tun (nur Ruhetage).")
        return 0

    client = _make_client()
    ok = 0
    errors = 0
    for s in workout_sessions:
        try:
            upload_and_schedule(s.workout, s.date, client=client)
            ok += 1
        except Exception as e:  # noqa: BLE001 — best-effort, alle Fehler loggen
            errors += 1
            print(f"FEHLER bei {s.date} {s.workout.name}: {e}", file=sys.stderr)

    print(f"FERTIG: {ok}/{len(workout_sessions)} hochgeladen, {errors} Fehler.")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
