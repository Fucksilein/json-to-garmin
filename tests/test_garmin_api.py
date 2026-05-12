"""Garmin-API-Adapter: korrigierte IDs, Step-Reihenfolge, Repeat-Übersetzung."""

from json_to_garmin import Repeat, Step, Target, Workout, to_garmin_dict
from json_to_garmin.garmin_api import (
    CONDITION_DISTANCE_ID,
    TARGET_HR_ID,
    TARGET_PACE_ZONE_ID,
    TARGET_POWER_ID,
)


def _segment(d):
    return d["workoutSegments"][0]["workoutSteps"]


def test_distance_condition_uses_corrected_id():
    w = Workout(
        name="x",
        sport="run",
        steps=[Step(kind="work", end="distance", value=1000)],
    )
    step = _segment(to_garmin_dict(w))[0]
    assert step["endCondition"]["conditionTypeId"] == CONDITION_DISTANCE_ID == 3


def test_pace_target_id_and_keys():
    w = Workout(
        name="x",
        sport="run",
        steps=[
            Step(
                kind="work",
                end="distance",
                value=1000,
                target=Target(kind="pace", pace_low="4:20", pace_high="4:40"),
            )
        ],
    )
    step = _segment(to_garmin_dict(w))[0]
    assert step["targetType"]["workoutTargetTypeId"] == TARGET_PACE_ZONE_ID == 5
    assert step["targetType"]["workoutTargetTypeKey"] == "pace.zone"
    # 4:20 → schneller → höhere m/s
    assert step["targetValueOne"] > step["targetValueTwo"]


def test_power_target_keys():
    w = Workout(
        name="x",
        sport="bike",
        steps=[
            Step(
                kind="work",
                end="time",
                value=900,
                target=Target(kind="power", low=246, high=266),
            )
        ],
    )
    step = _segment(to_garmin_dict(w))[0]
    assert step["targetType"]["workoutTargetTypeId"] == TARGET_POWER_ID
    assert step["targetType"]["workoutTargetTypeKey"] == "power.zone"
    assert step["targetValueOne"] == 246.0
    assert step["targetValueTwo"] == 266.0


def test_hr_zone_target_keys():
    w = Workout(
        name="x",
        sport="run",
        steps=[
            Step(
                kind="work",
                end="time",
                value=3600,
                target=Target(kind="hr_zone", zone=2),
            )
        ],
    )
    step = _segment(to_garmin_dict(w))[0]
    assert step["targetType"]["workoutTargetTypeId"] == TARGET_HR_ID == 4
    assert step["zoneNumber"] == 2


def test_repeat_translation():
    w = Workout(
        name="x",
        sport="bike",
        steps=[
            Step(kind="warmup", end="time", value=600),
            Repeat(
                iterations=3,
                steps=[
                    Step(kind="work", end="time", value=900),
                    Step(kind="recover", end="time", value=300),
                ],
            ),
            Step(kind="cooldown", end="time", value=600),
        ],
    )
    steps = _segment(to_garmin_dict(w))
    assert len(steps) == 3
    assert steps[1]["type"] == "RepeatGroupDTO"
    assert steps[1]["numberOfIterations"] == 3
    assert steps[1]["skipLastRestStep"] is True
    children = steps[1]["workoutSteps"]
    assert [c["stepOrder"] for c in children] == [1, 2]


def test_step_order_top_level():
    w = Workout(
        name="x",
        sport="bike",
        steps=[
            Step(kind="warmup", end="time", value=60),
            Step(kind="work", end="time", value=60),
            Step(kind="cooldown", end="time", value=60),
        ],
    )
    steps = _segment(to_garmin_dict(w))
    assert [s["stepOrder"] for s in steps] == [1, 2, 3]


def test_nested_repeat():
    w = Workout(
        name="x",
        sport="run",
        steps=[
            Repeat(
                iterations=2,
                steps=[
                    Repeat(
                        iterations=4,
                        steps=[
                            Step(kind="work", end="time", value=60),
                            Step(kind="recover", end="time", value=120),
                        ],
                    ),
                    Step(kind="recover", end="time", value=240),
                ],
            )
        ],
    )
    outer = _segment(to_garmin_dict(w))[0]
    assert outer["type"] == "RepeatGroupDTO"
    inner = outer["workoutSteps"][0]
    assert inner["type"] == "RepeatGroupDTO"
    assert inner["numberOfIterations"] == 4


def test_sport_to_workout_class():
    # Werte aus garminconnect.workout default factories (to_dict() Output)
    for sport, expected_key in [
        ("run", "running"),
        ("bike", "cycling"),
        ("swim", "swimming"),
        ("strength", "fitness_equipment"),
    ]:
        w = Workout(name="x", sport=sport, steps=[Step(kind="work", end="time", value=60)])
        d = to_garmin_dict(w)
        assert d["sportType"]["sportTypeKey"] == expected_key


def test_lap_button_end_condition():
    w = Workout(
        name="x",
        sport="swim",
        steps=[Step(kind="work", end="lap_button", value=None)],
    )
    step = _segment(to_garmin_dict(w))[0]
    assert step["endCondition"]["conditionTypeKey"] == "lap.button"
    # Garmin to_dict() lässt endConditionValue=None weg — egal, lap.button braucht keinen Wert
    assert step.get("endConditionValue") is None


# --- Multisport -------------------------------------------------------------

from json_to_garmin import Segment  # noqa: E402


def _make_sprint_triathlon() -> Workout:
    return Workout(
        name="Sprint Triathlon",
        sport="multisport",
        segments=[
            Segment(sport="swim", steps=[Step(kind="work", end="distance", value=750)]),
            Segment(sport="bike", steps=[Step(kind="work", end="distance", value=20000)]),
            Segment(sport="run", steps=[Step(kind="work", end="distance", value=5000)]),
        ],
    )


def test_multisport_top_level_sport_type():
    from json_to_garmin.garmin_api import SPORT_TYPE_MULTISPORT_ID
    d = to_garmin_dict(_make_sprint_triathlon())
    assert d["sportType"]["sportTypeKey"] == "multi_sport"
    assert d["sportType"]["sportTypeId"] == SPORT_TYPE_MULTISPORT_ID == 10


def test_multisport_segment_count():
    d = to_garmin_dict(_make_sprint_triathlon())
    assert len(d["workoutSegments"]) == 3


def test_multisport_segment_sport_types():
    d = to_garmin_dict(_make_sprint_triathlon())
    keys = [seg["sportType"]["sportTypeKey"] for seg in d["workoutSegments"]]
    assert keys == ["swimming", "cycling", "running"]


def test_multisport_segment_order():
    d = to_garmin_dict(_make_sprint_triathlon())
    orders = [seg["segmentOrder"] for seg in d["workoutSegments"]]
    assert orders == [1, 2, 3]


def test_multisport_steps_inside_segment():
    d = to_garmin_dict(_make_sprint_triathlon())
    swim_steps = d["workoutSegments"][0]["workoutSteps"]
    assert len(swim_steps) == 1
    assert swim_steps[0]["endCondition"]["conditionTypeId"] == CONDITION_DISTANCE_ID
