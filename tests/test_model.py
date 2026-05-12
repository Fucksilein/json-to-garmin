"""Modell-Validierung und JSON-Roundtrip."""

import pytest
from pydantic import ValidationError

from json_to_garmin import Repeat, Segment, Step, Target, Workout


def test_minimal_workout():
    w = Workout(
        name="x",
        sport="run",
        steps=[Step(kind="work", end="time", value=600)],
    )
    assert w.steps[0].target.kind == "none"


def test_repeat_recursive():
    inner = Repeat(
        iterations=4,
        steps=[
            Step(kind="work", end="time", value=60, target=Target(kind="hr_zone", zone=5)),
            Step(kind="recover", end="time", value=120),
        ],
    )
    outer = Repeat(iterations=2, steps=[inner, Step(kind="recover", end="time", value=240)])
    w = Workout(name="x", sport="run", steps=[outer])
    assert isinstance(w.steps[0], Repeat)
    assert isinstance(w.steps[0].steps[0], Repeat)


def test_iterations_must_be_positive():
    with pytest.raises(ValidationError):
        Repeat(iterations=0, steps=[])


def test_unknown_target_kind_rejected():
    with pytest.raises(ValidationError):
        Target(kind="lactate")  # type: ignore[arg-type]


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        Step(kind="work", end="time", value=60, foo=1)  # type: ignore[call-arg]


def test_json_roundtrip():
    w = Workout(
        name="rt",
        sport="bike",
        steps=[
            Step(kind="warmup", end="time", value=600),
            Repeat(
                iterations=3,
                steps=[
                    Step(
                        kind="work",
                        end="time",
                        value=900,
                        target=Target(kind="power", low=246, high=266),
                    ),
                    Step(kind="recover", end="time", value=300),
                ],
            ),
            Step(kind="cooldown", end="time", value=600),
        ],
    )
    js = w.model_dump_json()
    w2 = Workout.model_validate_json(js)
    assert w2 == w


def test_lap_button_step():
    s = Step(kind="work", end="lap_button", value=None)
    assert s.value is None


def test_pace_target_strings():
    t = Target(kind="pace", pace_low="4:20", pace_high="4:40")
    assert t.pace_low == "4:20"


# --- Multisport -------------------------------------------------------------


def test_multisport_valid():
    w = Workout(
        name="Triathlon",
        sport="multisport",
        segments=[
            Segment(sport="swim", steps=[Step(kind="work", end="distance", value=750)]),
            Segment(sport="bike", steps=[Step(kind="work", end="distance", value=20000)]),
            Segment(sport="run", steps=[Step(kind="work", end="distance", value=5000)]),
        ],
    )
    assert w.sport == "multisport"
    assert len(w.segments) == 3


def test_multisport_without_segments_rejected():
    with pytest.raises(ValidationError):
        Workout(name="x", sport="multisport")


def test_multisport_roundtrip():
    w = Workout(
        name="Duathlon",
        sport="multisport",
        segments=[
            Segment(sport="run", steps=[Step(kind="work", end="distance", value=5000)]),
            Segment(sport="bike", steps=[Step(kind="work", end="distance", value=20000)]),
            Segment(sport="run", steps=[Step(kind="work", end="distance", value=2500)]),
        ],
    )
    w2 = Workout.model_validate_json(w.model_dump_json())
    assert w2 == w


def test_single_sport_without_steps_rejected():
    with pytest.raises(ValidationError):
        Workout(name="x", sport="run")


def test_multisport_as_segment_sport_rejected():
    with pytest.raises(ValidationError):
        Segment(sport="multisport", steps=[Step(kind="work", end="time", value=60)])  # type: ignore[arg-type]
