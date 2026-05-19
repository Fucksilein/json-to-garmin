"""Convenience-Konstruktoren für häufige Workout-Muster.

Erzeugen `Workout`-Instanzen — Garmin-spezifisches Mapping passiert in
`garmin_api.to_garmin_dict`.
"""

from __future__ import annotations

from json_to_garmin.garmin_api import pace_to_ms
from json_to_garmin.model import Repeat, Step, StepKind, Target, Workout


def _offset_pace(pace_str: str, offset_secs: int) -> str:
    """'4:30' +/- N Sekunden → 'M:SS'."""
    parts = pace_str.split(":")
    total = int(parts[0]) * 60 + int(parts[1]) + offset_secs
    total = max(total, 1)
    return f"{total // 60}:{total % 60:02d}"


def _maybe_step(
    kind: StepKind, duration_min: float, target: Target | None = None
) -> Step | None:
    """Step für `duration_min` Minuten — oder None, wenn die Dauer 0 ist.

    Erlaubt Buildern, optionale WU/CD-Steps wegfallen zu lassen, ohne die
    Reihenfolge-Logik im Aufrufer zu verkomplizieren.
    """
    if duration_min <= 0:
        return None
    return Step(
        kind=kind,
        end="time",
        value=duration_min * 60,
        target=target or Target(kind="none"),
    )


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


def build_run_threshold(
    name: str,
    reps: int,
    interval_min: float,
    pace_low: str,
    pace_high: str,
    recover_min: float = 3.0,
    recover_hr_zone: int = 2,
    wu_min: float = 5.0,
    cd_min: float = 5.0,
) -> Workout:
    """Threshold-Run mit expliziten Pace-Grenzen pro Intervall.

    `pace_low` ist der schnellere Wert (z. B. "4:30"), `pace_high` der langsamere
    (z. B. "4:50"). Erholung als HR-Zone, WU/CD ohne Target.
    """
    interval = Step(
        kind="work",
        end="time",
        value=interval_min * 60,
        target=Target(kind="pace", pace_low=pace_low, pace_high=pace_high),
    )
    recover = Step(
        kind="recover",
        end="time",
        value=recover_min * 60,
        target=Target(kind="hr_zone", zone=recover_hr_zone),
    )
    repeat = Repeat(iterations=reps, steps=[interval, recover])

    steps: list[Step | Repeat] = []
    wu = _maybe_step("warmup", wu_min)
    if wu is not None:
        steps.append(wu)
    steps.append(repeat)
    cd = _maybe_step("cooldown", cd_min)
    if cd is not None:
        steps.append(cd)

    avg_pace_secs = (pace_to_ms(pace_low) + pace_to_ms(pace_high)) / 2.0
    est_interval_dist = interval_min * 60 * avg_pace_secs
    est_total = int(
        (wu_min + reps * (interval_min + recover_min) + cd_min) * 60
    )
    est_dist = (
        wu_min * 60 * 2.5
        + reps * (est_interval_dist + recover_min * 60 * 2.5)
        + cd_min * 60 * 2.5
    )

    return Workout(
        name=name,
        sport="run",
        steps=steps,
        estimated_duration_sec=est_total,
        estimated_distance_m=est_dist,
    )


def build_bike_intervals(
    name: str,
    reps: int,
    duration_min: float,
    watts_low: int | None = None,
    watts_high: int | None = None,
    warmup_min: float = 5.0,
    cooldown_min: float = 5.0,
    rest_min: float = 5.0,
    total_duration_min: float | None = None,
    ga1_watts_low: int | None = None,
    ga1_watts_high: int | None = None,
    *,
    zone: int | None = None,
    rest_zone: int = 2,
    wu_zone: int = 1,
    cd_zone: int = 1,
) -> Workout:
    """Bike-Intervalle in Watt- oder Power-Zone-Modus.

    Zwei sich ausschließende Modi:

    - **Zone-Modus** (`zone` gesetzt): Intervalle als `power_zone(zone)`,
      Erholung in `power_zone(rest_zone)`, WU/CD in `power_zone(wu_zone/cd_zone)`.
      `ga1_watts_*` und `total_duration_min` werden ignoriert.
    - **Watt-Modus** (`watts_low`/`watts_high` gesetzt): Intervalle als
      absolute Watt-Range; mit `total_duration_min` + `ga1_watts_*` wird die
      Restzeit als GA1-Auffüllblock ergänzt. Unverändertes Altverhalten.
    """
    if zone is not None:
        interval_target = Target(kind="power_zone", zone=zone)
        rest_target = Target(kind="power_zone", zone=rest_zone)
        wu_target = Target(kind="power_zone", zone=wu_zone)
        cd_target = Target(kind="power_zone", zone=cd_zone)

        steps: list[Step | Repeat] = []
        wu = _maybe_step("warmup", warmup_min, wu_target)
        if wu is not None:
            steps.append(wu)
        interval = Step(
            kind="work", end="time", value=duration_min * 60, target=interval_target
        )
        rest = Step(
            kind="recover", end="time", value=rest_min * 60, target=rest_target
        )
        steps.append(Repeat(iterations=reps, steps=[interval, rest]))
        cd = _maybe_step("cooldown", cooldown_min, cd_target)
        if cd is not None:
            steps.append(cd)

        block_min = reps * duration_min + (reps - 1) * rest_min
        est_total = int((warmup_min + block_min + cooldown_min) * 60)
        return Workout(
            name=name,
            sport="bike",
            steps=steps,
            estimated_duration_sec=est_total,
        )

    if watts_low is None or watts_high is None:
        raise ValueError(
            "build_bike_intervals braucht entweder `zone` (power_zone-Modus) "
            "oder `watts_low`+`watts_high` (Watt-Modus)."
        )

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
    steps = [wu, repeat]

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


def build_run_easy(
    name: str,
    duration_min: float,
    hr_zone: int,
    wu_min: float = 5.0,
    cd_min: float = 5.0,
    wu_hr_zone: int = 1,
    cd_hr_zone: int = 1,
) -> Workout:
    """Easy-Run mit WU/CD. `wu_min=0`/`cd_min=0` entfernt den jeweiligen Step."""
    main = Step(
        kind="work",
        end="time",
        value=duration_min * 60,
        target=Target(kind="hr_zone", zone=hr_zone),
    )
    steps: list[Step | Repeat] = []
    wu = _maybe_step("warmup", wu_min, Target(kind="hr_zone", zone=wu_hr_zone))
    if wu is not None:
        steps.append(wu)
    steps.append(main)
    cd = _maybe_step("cooldown", cd_min, Target(kind="hr_zone", zone=cd_hr_zone))
    if cd is not None:
        steps.append(cd)

    return Workout(
        name=name,
        sport="run",
        steps=steps,
        estimated_duration_sec=int((wu_min + duration_min + cd_min) * 60),
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


def build_bike_zone(
    name: str,
    duration_min: float,
    zone: int,
    wu_min: float = 5.0,
    cd_min: float = 5.0,
    wu_zone: int = 1,
    cd_zone: int = 1,
) -> Workout:
    """Bike-Easy mit Garmin-Power-Zonen — portabel über FTP-Änderungen."""
    main = Step(
        kind="work",
        end="time",
        value=duration_min * 60,
        target=Target(kind="power_zone", zone=zone),
    )
    steps: list[Step | Repeat] = []
    wu = _maybe_step("warmup", wu_min, Target(kind="power_zone", zone=wu_zone))
    if wu is not None:
        steps.append(wu)
    steps.append(main)
    cd = _maybe_step("cooldown", cd_min, Target(kind="power_zone", zone=cd_zone))
    if cd is not None:
        steps.append(cd)

    return Workout(
        name=name,
        sport="bike",
        steps=steps,
        estimated_duration_sec=int((wu_min + duration_min + cd_min) * 60),
    )


def build_gym(name: str, duration_min: float) -> Workout:
    step = Step(kind="work", end="time", value=duration_min * 60)
    return Workout(
        name=name,
        sport="strength",
        steps=[step],
        estimated_duration_sec=int(duration_min * 60),
    )


def build_swim(
    name: str,
    duration_min: float,
    wu_min: float = 5.0,
    cd_min: float = 5.0,
) -> Workout:
    """Easy-Swim mit optionalem WU/CD (kein Target). `wu_min=0`/`cd_min=0` entfernt den Step."""
    main = Step(kind="work", end="time", value=duration_min * 60)
    steps: list[Step | Repeat] = []
    wu = _maybe_step("warmup", wu_min)
    if wu is not None:
        steps.append(wu)
    steps.append(main)
    cd = _maybe_step("cooldown", cd_min)
    if cd is not None:
        steps.append(cd)

    return Workout(
        name=name,
        sport="swim",
        steps=steps,
        estimated_duration_sec=int((wu_min + duration_min + cd_min) * 60),
    )
