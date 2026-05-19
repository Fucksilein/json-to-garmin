"""Builder produzieren erwartete Workout-Struktur."""

import pytest

from json_to_garmin import (
    Repeat,
    Step,
    build_bike_easy,
    build_bike_intervals,
    build_bike_zone,
    build_gym,
    build_run_easy,
    build_run_intervals,
    build_run_threshold,
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


def test_bike_intervals_zone_mode():
    w = build_bike_intervals(
        name="Z4 SS", reps=4, duration_min=10, zone=4, rest_zone=2,
        warmup_min=10, cooldown_min=10, rest_min=5,
    )
    assert w.sport == "bike"
    assert len(w.steps) == 3
    assert w.steps[0].kind == "warmup"
    assert w.steps[0].target.kind == "power_zone"
    assert w.steps[0].target.zone == 1  # Default wu_zone

    repeat = w.steps[1]
    assert isinstance(repeat, Repeat) and repeat.iterations == 4
    interval, rest = repeat.steps
    assert interval.target.kind == "power_zone" and interval.target.zone == 4
    assert rest.target.kind == "power_zone" and rest.target.zone == 2

    assert w.steps[2].kind == "cooldown" and w.steps[2].target.zone == 1


def test_bike_intervals_requires_zone_or_watts():
    with pytest.raises(ValueError, match="zone.*watts"):
        build_bike_intervals(name="x", reps=3, duration_min=10)


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


def test_run_threshold_structure():
    w = build_run_threshold(
        name="Threshold", reps=4, interval_min=8,
        pace_low="4:00", pace_high="4:15",
        recover_min=2, recover_hr_zone=2,
    )
    assert w.sport == "run"
    # WU + Repeat + CD (Defaults wu=5, cd=5)
    assert len(w.steps) == 3
    assert w.steps[0].kind == "warmup" and w.steps[0].target.kind == "none"
    assert w.steps[2].kind == "cooldown" and w.steps[2].target.kind == "none"

    repeat = w.steps[1]
    assert isinstance(repeat, Repeat) and repeat.iterations == 4
    interval, recover = repeat.steps
    assert interval.target.kind == "pace"
    assert interval.target.pace_low == "4:00"
    assert interval.target.pace_high == "4:15"
    assert recover.target.kind == "hr_zone" and recover.target.zone == 2


def test_run_threshold_no_wu_cd():
    w = build_run_threshold(
        name="x", reps=2, interval_min=5,
        pace_low="4:20", pace_high="4:40",
        wu_min=0, cd_min=0,
    )
    # Nur Repeat ohne WU/CD
    assert len(w.steps) == 1
    assert isinstance(w.steps[0], Repeat)


def test_run_easy_default_wu_cd():
    w = build_run_easy("Easy 60", 60, 2)
    assert w.sport == "run"
    # WU (Z1) + Work (Z2) + CD (Z1)
    assert len(w.steps) == 3
    assert w.steps[0].kind == "warmup" and w.steps[0].target.zone == 1
    assert w.steps[1].kind == "work" and w.steps[1].target.zone == 2
    assert w.steps[2].kind == "cooldown" and w.steps[2].target.zone == 1


def test_run_easy_no_wu_cd():
    w = build_run_easy("x", 60, 2, wu_min=0, cd_min=0)
    assert len(w.steps) == 1
    assert w.steps[0].target.kind == "hr_zone"
    assert w.steps[0].target.zone == 2


def test_bike_easy_power_range():
    w = build_bike_easy("x", 75, 154, 210)
    assert w.steps[0].target.kind == "power"
    assert w.steps[0].target.low == 154


def test_bike_zone_structure():
    w = build_bike_zone("Z3 SS", duration_min=60, zone=3)
    assert w.sport == "bike"
    # WU (Z1) + Work (Z3) + CD (Z1) — Defaults wu=5, cd=5
    assert len(w.steps) == 3
    assert w.steps[0].kind == "warmup" and w.steps[0].target.zone == 1
    assert w.steps[1].kind == "work" and w.steps[1].target.kind == "power_zone"
    assert w.steps[1].target.zone == 3
    assert w.steps[2].kind == "cooldown" and w.steps[2].target.zone == 1


def test_bike_zone_no_wu_cd():
    w = build_bike_zone("x", duration_min=45, zone=2, wu_min=0, cd_min=0)
    assert len(w.steps) == 1
    assert w.steps[0].target.kind == "power_zone"
    assert w.steps[0].target.zone == 2


def test_gym_no_target():
    w = build_gym("x", 30)
    assert w.sport == "strength"
    assert w.steps[0].target.kind == "none"


def test_swim_default_wu_cd():
    w = build_swim("Easy", 45)
    assert w.sport == "swim"
    # WU + Work + CD — alle ohne Target
    assert len(w.steps) == 3
    assert all(s.target.kind == "none" for s in w.steps)
    assert [s.kind for s in w.steps] == ["warmup", "work", "cooldown"]


def test_swim_no_wu_cd():
    w = build_swim("x", 60, wu_min=0, cd_min=0)
    assert len(w.steps) == 1
    assert w.steps[0].target.kind == "none"
