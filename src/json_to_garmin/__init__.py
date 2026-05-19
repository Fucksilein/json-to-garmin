from importlib.metadata import PackageNotFoundError, version

from json_to_garmin.builders import (
    build_bike_easy,
    build_bike_intervals,
    build_bike_zone,
    build_gym,
    build_run_easy,
    build_run_intervals,
    build_run_threshold,
    build_swim,
)
from json_to_garmin.garmin_api import (
    delete_uploaded,
    to_garmin_dict,
    upload_and_schedule,
)
from json_to_garmin.model import (
    EndCondition,
    Repeat,
    Segment,
    SingleSport,
    Sport,
    Step,
    StepKind,
    Target,
    TargetKind,
    Workout,
)

try:
    __version__ = version("json-to-garmin")
except PackageNotFoundError:  # paket nicht installiert (z. B. lokaler Quell-Checkout ohne pip install)
    __version__ = "0.0.0+unknown"

__all__ = [
    "EndCondition",
    "Repeat",
    "Segment",
    "SingleSport",
    "Sport",
    "Step",
    "StepKind",
    "Target",
    "TargetKind",
    "Workout",
    "__version__",
    "build_bike_easy",
    "build_bike_intervals",
    "build_bike_zone",
    "build_gym",
    "build_run_easy",
    "build_run_intervals",
    "build_run_threshold",
    "build_swim",
    "delete_uploaded",
    "to_garmin_dict",
    "upload_and_schedule",
]
