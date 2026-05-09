"""schema.json aus model.Workout regenerieren."""

import json
from pathlib import Path

from json_to_garmin.model import Workout

ROOT = Path(__file__).parent.parent
schema = Workout.model_json_schema()
(ROOT / "schema.json").write_text(json.dumps(schema, indent=2) + "\n")
print("schema.json regeneriert.")
