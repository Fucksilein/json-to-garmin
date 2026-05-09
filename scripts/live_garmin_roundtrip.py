"""Live-Roundtrip gegen Garmin Connect.

Lädt alle Workouts aus `example_all.json` hoch, plant sie auf heute…heute+6 Tage,
pausiert für manuelle Inspektion und löscht sie anschließend wieder.

Usage:
    export GARMIN_EMAIL=...
    export GARMIN_PASSWORD=...
    poetry run python scripts/live_garmin_roundtrip.py            # Standard-Flow
    poetry run python scripts/live_garmin_roundtrip.py --dry-run  # nur Dicts ausgeben
    poetry run python scripts/live_garmin_roundtrip.py --keep     # keinen Cleanup-Prompt
    poetry run python scripts/live_garmin_roundtrip.py --cleanup-only  # State-Datei abräumen

State-Datei: scripts/.live_test_state.json — enthält die IDs der hochgeladenen
Workouts. Falls das Skript zwischen Upload und Cleanup abbricht, kann via
`--cleanup-only` aufgeräumt werden.

Token-Cache: ~/.garminconnect (überschreibbar via GARMINTOKENS env var).
Beim ersten Login wird ggf. nach MFA gefragt; danach läuft es ohne Interaktion.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from json_to_garmin import Workout, delete_uploaded, to_garmin_dict, upload_and_schedule

ROOT = Path(__file__).parent.parent
EXAMPLES = ROOT / "example_all.json"
STATE_FILE = Path(__file__).parent / ".live_test_state.json"
DOTENV = ROOT / ".env"
NAME_PREFIX = "[live-test] "
CALENDAR_URL = "https://connect.garmin.com/modern/calendar"


def load_dotenv() -> None:
    """Lädt KEY=VALUE Zeilen aus .env in os.environ (ohne python-dotenv-Dependency).

    Toleriert Whitespace um `=`, ignoriert Leerzeilen und `#`-Kommentare.
    Vorhandene Env-Vars werden nicht überschrieben.
    """
    if not DOTENV.exists():
        return
    for line in DOTENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_examples() -> list[Workout]:
    raw = json.loads(EXAMPLES.read_text())
    workouts: list[Workout] = []
    for w_raw in raw["workouts"]:
        clean = {k: v for k, v in w_raw.items() if not k.startswith("_")}
        clean["name"] = NAME_PREFIX + clean["name"]
        workouts.append(Workout.model_validate(clean))
    return workouts


def make_client():
    """garminconnect.Garmin mit Token-Cache. MFA-Prompt im Terminal falls nötig."""
    from garminconnect import Garmin

    email = os.environ.get("GARMIN_EMAIL") or os.environ.get("GARMIN_USER")
    password = os.environ.get("GARMIN_PASSWORD")
    if not email or not password:
        sys.exit("FEHLER: GARMIN_EMAIL/GARMIN_USER und GARMIN_PASSWORD müssen gesetzt sein.")

    tokenstore = os.environ.get("GARMINTOKENS") or str(Path.home() / ".garminconnect")
    client = Garmin(email, password, prompt_mfa=lambda: input("Garmin MFA-Code: "))
    client.login(tokenstore=tokenstore)
    return client


def confirm(prompt: str) -> bool:
    answer = input(f"{prompt} [y/N]: ").strip().lower()
    return answer in ("y", "yes", "j", "ja")


def save_state(state: list[dict]) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def load_state() -> list[dict]:
    if not STATE_FILE.exists():
        return []
    return json.loads(STATE_FILE.read_text())


def cleanup(state: list[dict], client) -> int:
    """Best-Effort Cleanup. Gibt Anzahl Fehler zurück."""
    errors = 0
    for entry in state:
        try:
            delete_uploaded(
                entry["workout_id"],
                entry.get("scheduled_workout_id"),
                client=client,
            )
        except Exception as e:  # noqa: BLE001 — bewusst broad: ein Fehler darf andere nicht stoppen
            errors += 1
            print(f"  FEHLER bei {entry.get('name', entry)}: {e}")
    return errors


def check_name_collisions(client, planned_names: list[str]) -> list[str]:
    """Sucht in der Garmin-Workout-Bibliothek nach Namensgleichheit."""
    existing = client.get_workouts(0, 200)
    existing_names = {w.get("workoutName") for w in existing}
    return [n for n in planned_names if n in existing_names]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="kein Login, nur Workout-Dicts")
    parser.add_argument("--keep", action="store_true", help="kein Cleanup-Prompt")
    parser.add_argument("--cleanup-only", action="store_true", help="nur State-Datei abräumen")
    args = parser.parse_args()

    load_dotenv()

    if args.cleanup_only:
        state = load_state()
        if not state:
            print("Keine State-Datei vorhanden — nichts zu tun.")
            return 0
        print(f"Lese {len(state)} Einträge aus {STATE_FILE}.")
        if not confirm(f"Wirklich {len(state)} Workouts auf Garmin löschen?"):
            return 1
        client = make_client()
        errors = cleanup(state, client)
        if errors == 0:
            STATE_FILE.unlink()
            print("Cleanup OK, State-Datei entfernt.")
        else:
            print(f"{errors} Fehler — State-Datei behalten zur erneuten Ausführung.")
        return errors

    workouts = load_examples()
    today = date.today()
    schedule = [(w, today + timedelta(days=i)) for i, w in enumerate(workouts)]

    print(f"\n{len(workouts)} Workouts werden hochgeladen + eingeplant:\n")
    for w, d in schedule:
        print(f"  {d.isoformat()}  {w.sport:10s}  {w.name}")
    print()

    if args.dry_run:
        for w, _ in schedule:
            to_garmin_dict(w)  # validiert die Übersetzung
            print(f"[dry-run] OK: {w.name}")
        return 0

    if STATE_FILE.exists():
        sys.exit(
            f"FEHLER: State-Datei {STATE_FILE} existiert bereits. "
            "Vorherigen Lauf erst mit --cleanup-only abräumen."
        )

    if not confirm("Weiter?"):
        return 1

    client = make_client()

    collisions = check_name_collisions(client, [w.name for w, _ in schedule])
    if collisions:
        sys.exit(
            "FEHLER: Workouts mit diesen Namen existieren bereits in Garmin Connect:\n  "
            + "\n  ".join(collisions)
            + "\nBitte dort manuell entfernen und erneut versuchen."
        )

    state: list[dict] = []
    try:
        for w, d in schedule:
            result = upload_and_schedule(w, d.isoformat(), client=client)
            assert result is not None
            state.append(
                {
                    "name": w.name,
                    "workout_id": result["workout_id"],
                    "scheduled_workout_id": result["scheduled_workout_id"],
                }
            )
            save_state(state)
    except Exception as e:
        save_state(state)
        sys.exit(
            f"FEHLER beim Upload: {e}\n"
            f"Bisher erfolgreich: {len(state)} — mit --cleanup-only abräumen."
        )

    print(f"\n{len(state)} Workouts hochgeladen. State: {STATE_FILE}")
    print(f"Im Kalender prüfen: {CALENDAR_URL}\n")

    if args.keep:
        print("--keep gesetzt: kein Cleanup. Später mit --cleanup-only entfernen.")
        return 0

    input("Enter drücken, um alle Workouts wieder zu löschen... ")
    errors = cleanup(state, client)
    if errors == 0:
        STATE_FILE.unlink()
        print("Cleanup OK, State-Datei entfernt.")
    else:
        print(f"{errors} Fehler — State-Datei behalten, mit --cleanup-only erneut versuchen.")
    return errors


if __name__ == "__main__":
    raise SystemExit(main())
