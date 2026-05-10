"""CLI-Entry-Point — JSON-Workouts validieren / hochladen / planen.

Usage:
    json-to-garmin <file.json> --dryrun
    json-to-garmin <file.json> --date YYYY-MM-DD   # benötigt GARMIN_EMAIL/PASSWORD

Akzeptiert das Wrapper-Format `{"workouts": [...]}` (mit optionalen `_label`/`_comment`-Meta-Keys)
oder ein einzelnes Workout-Objekt.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from json_to_garmin.garmin_api import to_garmin_dict, upload_and_schedule
from json_to_garmin.model import Workout


def _parse_workouts(path: Path) -> list[Workout]:
    """Lädt JSON. Akzeptiert Wrapper-Format `{"workouts": [...]}` oder ein einzelnes Workout."""
    raw = json.loads(path.read_text())
    if isinstance(raw, dict) and "workouts" in raw:
        items = raw["workouts"]
    else:
        items = [raw]
    out: list[Workout] = []
    for item in items:
        clean = {k: v for k, v in item.items() if not k.startswith("_")}
        out.append(Workout.model_validate(clean))
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


if __name__ == "__main__":
    raise SystemExit(main())
