"""schema.json aus model.Workout regenerieren.

Emittiert ein Top-Level-`oneOf` mit beiden vom CLI akzeptierten Formaten:

- bare Workout: das einzelne Modell-Objekt (mit optionalem `$schema`-Feld für Editor-Bindung).
- Wrapper: `{ "$schema"?, "_comment"?, "workouts": [WorkoutEntry, ...] }`, wobei jede
  Eintrag-Variante zusätzlich ein optionales `_label` zulässt.

Damit validiert das Schema sowohl `example_all.json` (Wrapper) als auch eine einzelne
Workout-Datei in einem Editor wie JetBrains/VS Code.
"""

import json
from pathlib import Path

from json_to_garmin.model import Workout

ROOT = Path(__file__).parent.parent

base = Workout.model_json_schema()
defs = base.pop("$defs", {})
base.pop("title", None)

# Editor-Convenience: `$schema` als String-Hint.
SCHEMA_PROP = {"type": "string"}

# Bare-Variante: Workout + erlaubtes `$schema`-Feld.
bare = dict(base)
bare["properties"] = {**bare["properties"], "$schema": SCHEMA_PROP}

# Wrapper-Eintrag: Workout + optionales `_label` für Doku-Hinweise.
entry = dict(base)
entry["properties"] = {**entry["properties"], "_label": {"type": "string"}}

defs["WorkoutBare"] = bare
defs["WorkoutEntry"] = entry

defs["Wrapper"] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["workouts"],
    "properties": {
        "$schema": SCHEMA_PROP,
        "_comment": {"type": "string"},
        "workouts": {
            "type": "array",
            "items": {"$ref": "#/$defs/WorkoutEntry"},
        },
    },
}

root = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "JsonToGarmin",
    "oneOf": [
        {"$ref": "#/$defs/WorkoutBare"},
        {"$ref": "#/$defs/Wrapper"},
    ],
    "$defs": defs,
}

(ROOT / "schema.json").write_text(json.dumps(root, indent=2) + "\n")
print("schema.json regeneriert.")
