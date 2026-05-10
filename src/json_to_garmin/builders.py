"""Convenience-Konstruktoren für häufige Workout-Muster.

Erzeugen `Workout`-Instanzen — Garmin-spezifisches Mapping passiert in
`garmin_api.to_garmin_dict`.
"""

from __future__ import annotations

from json_to_garmin.garmin_api import pace_to_ms
from json_to_garmin.model import Repeat, Step, Target, Workout


def _offset_pace(pace_str: str, offset_secs: int) -> str:
    """'4:30' +/- N Sekunden → 'M:SS'."""
    parts = pace_str.split(":")
    total = int(parts[0]) * 60 + int(parts[1]) + offset_secs
    total = max(total, 1)
    return f"{total // 60}:{total % 60:02d}"


def build_run_intervals(
    name: str,
    reps: int,
    interval_dist_m: float,
    interval_pace: str,
    interval_pace_window: int,
    recovery_dist_m: float,
    recovery_hr_zone: int,
    warmup_min: float,
    cooldown_min: float,
) -> Workout:
    fast = _offset_pace(interval_pace, -interval_pace_window)
    slow = _offset_pace(interval_pace, +interval_pace_window)

    wu = Step(kind="warmup", end="time", value=warmup_min * 60)
    interval = Step(
        kind="work",
        end="distance",
        value=interval_dist_m,
        target=Target(kind="pace", pace_low=fast, pace_high=slow),
    )
    recovery = Step(
        kind="recover",
        end="distance",
        value=recovery_dist_m,
        target=Target(kind="hr_zone", zone=recovery_hr_zone),
    )
    cd = Step(kind="cooldown", end="time", value=cooldown_min * 60)
    repeat = Repeat(iterations=reps, steps=[interval, recovery])

    est_interval_secs = interval_dist_m / pace_to_ms(interval_pace)
    est_recovery_secs = recovery_dist_m / 2.0
    est_total = int(
        warmup_min * 60 + reps * (est_interval_secs + est_recovery_secs) + cooldown_min * 60
    )
    est_dist = (
        warmup_min * 60 * 2.5
        + reps * (interval_dist_m + recovery_dist_m)
        + cooldown_min * 60 * 2.5
    )

    return Workout(
        name=name,
        sport="run",
        steps=[wu, repeat, cd],
        estimated_duration_sec=est_total,
        estimated_distance_m=est_dist,
    )


def build_bike_intervals(
    name: str,
    reps: int,
    duration_min: float,
    watts_low: int,
    watts_high: int,
    warmup_min: float,
    cooldown_min: float,
    rest_min: float = 3.0,
    total_duration_min: float | None = None,
    ga1_watts_low: int | None = None,
    ga1_watts_high: int | None = None,
) -> Workout:
    """Bike-Intervalle. Mit `total_duration_min` + `ga1_watts_*`: Restzeit als GA1-Block."""
    ga1 = (
        Target(kind="power", low=ga1_watts_low, high=ga1_watts_high)
        if ga1_watts_low is not None and ga1_watts_high is not None
        else Target(kind="none")
    )

    wu = Step(kind="warmup", end="time", value=warmup_min * 60, target=ga1)
    interval = Step(
        kind="work",
        end="time",
        value=duration_min * 60,
        target=Target(kind="power", low=watts_low, high=watts_high),
    )
    rest = Step(kind="recover", end="time", value=rest_min * 60, target=ga1)
    repeat = Repeat(iterations=reps, steps=[interval, rest])

    block_min = reps * duration_min + (reps - 1) * rest_min
    steps: list = [wu, repeat]

    if total_duration_min and ga1.kind != "none":
        ga1_remaining = total_duration_min - warmup_min - block_min - cooldown_min
        ga1_remaining = max(ga1_remaining, 0)
        if ga1_remaining > 0:
            steps.append(
                Step(kind="work", end="time", value=ga1_remaining * 60, target=ga1)
            )
        est_total = int(total_duration_min * 60)
    else:
        est_total = int((warmup_min + block_min + cooldown_min) * 60)

    steps.append(Step(kind="cooldown", end="time", value=cooldown_min * 60, target=ga1))

    return Workout(
        name=name,
        sport="bike",
        steps=steps,
        estimated_duration_sec=est_total,
    )


def build_run_easy(name: str, duration_min: float, hr_zone: int) -> Workout:
    step = Step(
        kind="work",
        end="time",
        value=duration_min * 60,
        target=Target(kind="hr_zone", zone=hr_zone),
    )
    return Workout(
        name=name,
        sport="run",
        steps=[step],
        estimated_duration_sec=int(duration_min * 60),
    )


def build_bike_easy(
    name: str, duration_min: float, watts_low: int, watts_high: int
) -> Workout:
    step = Step(
        kind="work",
        end="time",
        value=duration_min * 60,
        target=Target(kind="power", low=watts_low, high=watts_high),
    )
    return Workout(
        name=name,
        sport="bike",
        steps=[step],
        estimated_duration_sec=int(duration_min * 60),
    )


def build_gym(name: str, duration_min: float) -> Workout:
    step = Step(kind="work", end="time", value=duration_min * 60)
    return Workout(
        name=name,
        sport="strength",
        steps=[step],
        estimated_duration_sec=int(duration_min * 60),
    )


def build_swim(name: str, duration_min: float) -> Workout:
    step = Step(kind="work", end="time", value=duration_min * 60)
    return Workout(
        name=name,
        sport="swim",
        steps=[step],
        estimated_duration_sec=int(duration_min * 60),
    )
