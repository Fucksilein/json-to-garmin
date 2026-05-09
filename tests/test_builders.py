"""Builder produzieren erwartete Workout-Struktur."""

from json_to_garmin import (
    Repeat,
    Step,
    build_bike_easy,
    build_bike_intervals,
    build_gym,
    build_run_easy,
    build_run_intervals,
    build_swim,
)


def test_bike_intervals_with_ga1():
    w = build_bike_intervals(
        name="SS",
        reps=3,
        duration_min=15,
        watts_low=246,
        watts_high=266,
        warmup_min=15,
        cooldown_min=15,
        rest_min=5,
        total_duration_min=90,
        ga1_watts_low=154,
        ga1_watts_high=210,
    )
    assert w.sport == "bike"
    # WU + Repeat + GA1-Block + CD
    assert len(w.steps) == 4
    assert isinstance(w.steps[0], Step) and w.steps[0].kind == "warmup"
    assert isinstance(w.steps[1], Repeat) and w.steps[1].iterations == 3
    assert isinstance(w.steps[2], Step) and w.steps[2].kind == "work"
    assert isinstance(w.steps[3], Step) and w.steps[3].kind == "cooldown"
    # Repeat-Kinder: work + recover
    assert [s.kind for s in w.steps[1].steps] == ["work", "recover"]
    # WU/CD/Rest tragen GA1-Power
    assert w.steps[0].target.low == 154 and w.steps[0].target.high == 210


def test_bike_intervals_no_ga1():
    w = build_bike_intervals(
        name="x", reps=3, duration_min=12, watts_low=246, watts_high=266,
        warmup_min=10, cooldown_min=10, rest_min=3,
    )
    # Ohne GA1: WU + Repeat + CD (kein GA1-Block)
    assert len(w.steps) == 3
    assert w.steps[0].target.kind == "none"


def test_run_intervals_pace_offset():
    w = build_run_intervals(
        name="x", reps=5, interval_dist_m=1000, interval_pace="4:30",
        interval_pace_window=10, recovery_dist_m=1000, recovery_hr_zone=2,
        warmup_min=10, cooldown_min=10,
    )
    repeat = w.steps[1]
    assert isinstance(repeat, Repeat)
    interval = repeat.steps[0]
    assert interval.target.kind == "pace"
    assert interval.target.pace_low == "4:20"  # 10s schneller
    assert interval.target.pace_high == "4:40"  # 10s langsamer


def test_run_easy_hr_zone():
    w = build_run_easy("x", 60, 2)
    assert len(w.steps) == 1
    assert w.steps[0].target.kind == "hr_zone"
    assert w.steps[0].target.zone == 2


def test_bike_easy_power_range():
    w = build_bike_easy("x", 75, 154, 210)
    assert w.steps[0].target.kind == "power"
    assert w.steps[0].target.low == 154


def test_gym_no_target():
    w = build_gym("x", 30)
    assert w.sport == "strength"
    assert w.steps[0].target.kind == "none"


def test_swim_no_target():
    w = build_swim("x", 90)
    assert w.sport == "swim"
