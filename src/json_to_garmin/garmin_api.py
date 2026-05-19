"""Workout (generisches Modell) → Garmin Connect API.

Verwendet die Pydantic-Modelle aus `garminconnect.workout` für Serialisierung.
Korrigierte API-IDs wo die Library falsche Werte hat (zuletzt validiert
2026-05-09 via scripts/live_garmin_roundtrip.py):

- ConditionType.DISTANCE: Library 1, API 3
- pace.zone Target-Type-ID: 5 (für key "pace.zone")

Power und HR nutzen die Library-Werte direkt.
"""

from __future__ import annotations

import json

from garminconnect.workout import (
    ConditionType,
    CyclingWorkout,
    ExecutableStep,
    FitnessEquipmentWorkout,
    MultiSportWorkout,
    RepeatGroup,
    RunningWorkout,
    StepType,
    SwimmingWorkout,
    TargetType,
    WorkoutSegment,
)

from json_to_garmin.model import Repeat, Segment, Sport, Step, Target, Workout

# --- Korrigierte API-IDs ----------------------------------------------------

CONDITION_DISTANCE_ID = 3       # Library: 1
TARGET_PACE_ZONE_ID = 5         # für key "pace.zone"
TARGET_POWER_ID = TargetType.POWER
TARGET_HR_ID = TargetType.HEART_RATE
TARGET_NO_TARGET_ID = TargetType.NO_TARGET
SPORT_TYPE_MULTISPORT_ID = 10   # Library: 5 (falsch — 5 ist Krafttraining)

# Kandidaten-Methoden zum Entplanen eines Workouts — robust gegen
# Versionsdrift / Forks der garminconnect-Library.
_UNSCHEDULE_METHOD_CANDIDATES = (
    "unschedule_workout",
    "delete_workout_schedule",
    "remove_workout_scheduled",
)

# --- Step-Type Dicts --------------------------------------------------------

_STEP_KIND_MAP = {
    "warmup": (StepType.WARMUP, "warmup"),
    "work": (StepType.INTERVAL, "interval"),
    "recover": (StepType.RECOVERY, "recovery"),
    "rest": (StepType.REST, "rest"),
    "cooldown": (StepType.COOLDOWN, "cooldown"),
    "other": (StepType.INTERVAL, "interval"),
}


def _step_type_dict(kind: str) -> dict:
    step_id, key = _STEP_KIND_MAP[kind]
    return {"stepTypeId": step_id, "stepTypeKey": key, "displayOrder": step_id}


_REPEAT_TYPE = {
    "stepTypeId": StepType.REPEAT,
    "stepTypeKey": "repeat",
    "displayOrder": StepType.REPEAT,
}

_NO_TARGET = {
    "workoutTargetTypeId": TARGET_NO_TARGET_ID,
    "workoutTargetTypeKey": "no.target",
    "displayOrder": 1,
}

# --- Sport → Workout-Klasse + sportType -------------------------------------

_SPORT_TO_WORKOUT_CLS = {
    "run": RunningWorkout,
    "bike": CyclingWorkout,
    "swim": SwimmingWorkout,
    "strength": FitnessEquipmentWorkout,
    "multisport": MultiSportWorkout,
    "other": FitnessEquipmentWorkout,
}


def _workout_cls_for(sport: Sport):
    return _SPORT_TO_WORKOUT_CLS[sport]


def _sport_type_for(sport: str) -> dict:
    """Gibt den sportType-Dict für einen Einzel-Sport zurück (für Segment-Einträge)."""
    cls = _SPORT_TO_WORKOUT_CLS[sport]
    return cls.model_fields["sportType"].default_factory()


# --- End-Conditions ---------------------------------------------------------


def _end_condition(end: str, value: float | None) -> tuple[dict, float | None]:
    if end == "time":
        return (
            {
                "conditionTypeId": ConditionType.TIME,
                "conditionTypeKey": "time",
                "displayOrder": 2,
                "displayable": True,
            },
            float(value) if value is not None else None,
        )
    if end == "distance":
        return (
            {
                "conditionTypeId": CONDITION_DISTANCE_ID,
                "conditionTypeKey": "distance",
                "displayOrder": 3,
                "displayable": True,
            },
            float(value) if value is not None else None,
        )
    if end == "lap_button":
        return (
            {
                "conditionTypeId": 1,
                "conditionTypeKey": "lap.button",
                "displayOrder": 1,
                "displayable": True,
            },
            None,
        )
    if end == "calories":
        return (
            {
                "conditionTypeId": ConditionType.CALORIES,
                "conditionTypeKey": "calories",
                "displayOrder": 4,
                "displayable": True,
            },
            float(value) if value is not None else None,
        )
    raise ValueError(f"Unbekannte EndCondition: {end}")


def _iterations_condition(n: int) -> tuple[dict, float]:
    return (
        {
            "conditionTypeId": ConditionType.ITERATIONS,
            "conditionTypeKey": "iterations",
            "displayOrder": 7,
            "displayable": False,
        },
        float(n),
    )


# --- Pace-Helper ------------------------------------------------------------


def pace_to_ms(pace_str: str) -> float:
    """'4:30' → m/s (1000 / (4.5 * 60) = 3.704)."""
    parts = pace_str.split(":")
    minutes = int(parts[0]) + int(parts[1]) / 60
    return round(1000 / (minutes * 60), 7)


# --- Target → Garmin-Dict ---------------------------------------------------


def _target_dict(t: Target) -> dict:
    if t.kind == "none":
        return {
            "targetType": _NO_TARGET,
            "targetValueOne": None,
            "targetValueTwo": None,
            "zoneNumber": None,
        }
    if t.kind == "power":
        return {
            "targetType": {
                "workoutTargetTypeId": TARGET_POWER_ID,
                "workoutTargetTypeKey": "power.zone",
                "displayOrder": TARGET_POWER_ID,
            },
            "targetValueOne": float(t.low) if t.low is not None else None,
            "targetValueTwo": float(t.high) if t.high is not None else None,
            "zoneNumber": None,
        }
    if t.kind == "power_zone":
        return {
            "targetType": {
                "workoutTargetTypeId": TARGET_POWER_ID,
                "workoutTargetTypeKey": "power.zone",
                "displayOrder": TARGET_POWER_ID,
            },
            "targetValueOne": None,
            "targetValueTwo": None,
            "zoneNumber": t.zone,
        }
    if t.kind == "hr_zone":
        return {
            "targetType": {
                "workoutTargetTypeId": TARGET_HR_ID,
                "workoutTargetTypeKey": "heart.rate.zone",
                "displayOrder": TARGET_HR_ID,
            },
            "targetValueOne": None,
            "targetValueTwo": None,
            "zoneNumber": t.zone,
        }
    if t.kind == "pace":
        # low = schneller (höhere m/s), high = langsamer (niedrigere m/s)
        low_ms = pace_to_ms(t.pace_low) if t.pace_low else None
        high_ms = pace_to_ms(t.pace_high) if t.pace_high else None
        return {
            "targetType": {
                "workoutTargetTypeId": TARGET_PACE_ZONE_ID,
                "workoutTargetTypeKey": "pace.zone",
                "displayOrder": TARGET_PACE_ZONE_ID,
            },
            "targetValueOne": low_ms,
            "targetValueTwo": high_ms,
            "zoneNumber": None,
        }
    if t.kind == "cadence":
        return {
            "targetType": {
                "workoutTargetTypeId": TargetType.CADENCE,
                "workoutTargetTypeKey": "cadence.zone",
                "displayOrder": TargetType.CADENCE,
            },
            "targetValueOne": float(t.low) if t.low is not None else None,
            "targetValueTwo": float(t.high) if t.high is not None else None,
            "zoneNumber": t.zone,
        }
    if t.kind == "speed":
        return {
            "targetType": {
                "workoutTargetTypeId": TargetType.SPEED,
                "workoutTargetTypeKey": "speed.zone",
                "displayOrder": TargetType.SPEED,
            },
            "targetValueOne": float(t.low) if t.low is not None else None,
            "targetValueTwo": float(t.high) if t.high is not None else None,
            "zoneNumber": t.zone,
        }
    raise ValueError(f"Unbekannter Target-Kind: {t.kind}")


# --- Step-Konvertierung -----------------------------------------------------


def _build_executable(step: Step, step_order: int) -> ExecutableStep:
    cond, val = _end_condition(step.end, step.value)
    target = _target_dict(step.target)
    return ExecutableStep(
        stepOrder=step_order,
        stepType=_step_type_dict(step.kind),
        endCondition=cond,
        endConditionValue=val,
        targetType=target["targetType"],
        targetValueOne=target["targetValueOne"],
        targetValueTwo=target["targetValueTwo"],
        zoneNumber=target.get("zoneNumber"),
        description=step.note,
    )


def _build_repeat(rep: Repeat, step_order: int) -> RepeatGroup:
    children = _build_children(rep.steps)
    cond, val = _iterations_condition(rep.iterations)
    return RepeatGroup(
        stepOrder=step_order,
        stepType=_REPEAT_TYPE,
        numberOfIterations=rep.iterations,
        workoutSteps=children,
        endCondition=cond,
        endConditionValue=val,
        childStepId=1,
        smartRepeat=False,
        skipLastRestStep=rep.skip_last_rest,
    )


def _build_children(steps: list, start_order: int = 1) -> list:
    out: list = []
    order = start_order
    for s in steps:
        if isinstance(s, Step):
            out.append(_build_executable(s, order))
        elif isinstance(s, Repeat):
            out.append(_build_repeat(s, order))
        else:
            raise TypeError(f"Unerwarteter Step-Typ: {type(s)}")
        order += 1
    return out


# --- Workout → API-Dict -----------------------------------------------------


def _to_garmin_dict_multisport(workout: Workout) -> dict:
    """Übersetzt ein Multisport-Workout in das Garmin-API-Dict.

    stepOrder muss global einmalig über alle Segmente sein — Garmin lehnt Duplikate ab.
    """
    segments = []
    global_order = 1
    for i, seg in enumerate(workout.segments, 1):  # type: ignore[union-attr]
        sport_type = _sport_type_for(seg.sport)
        children = _build_children(seg.steps, start_order=global_order)
        global_order += len(seg.steps)
        segments.append(WorkoutSegment(segmentOrder=i, sportType=sport_type, workoutSteps=children))

    api = MultiSportWorkout(
        workoutName=workout.name,
        estimatedDurationInSecs=workout.estimated_duration_sec or 0,
        workoutSegments=segments,
    )
    result = api.to_dict()
    # Library hat sportTypeId=5 (Krafttraining) — korrekt ist 10 (multi_sport)
    result["sportType"] = {
        "sportTypeId": SPORT_TYPE_MULTISPORT_ID,
        "sportTypeKey": "multi_sport",
        "displayOrder": 4,
    }
    if workout.estimated_distance_m is not None:
        result["estimatedDistanceInMeters"] = workout.estimated_distance_m
    if workout.description is not None:
        result["description"] = workout.description
    return result


def to_garmin_dict(workout: Workout) -> dict:
    """Übersetzt ein generisches Workout in das Garmin-API-Dict."""
    if workout.sport == "multisport":
        return _to_garmin_dict_multisport(workout)

    cls = _workout_cls_for(workout.sport)
    sport_type = cls.model_fields["sportType"].default_factory()
    children = _build_children(workout.steps)

    segment = WorkoutSegment(
        segmentOrder=1,
        sportType=sport_type,
        workoutSteps=children,
    )

    api = cls(
        workoutName=workout.name,
        estimatedDurationInSecs=workout.estimated_duration_sec or 0,
        workoutSegments=[segment],
    )

    result = api.to_dict()
    if workout.estimated_distance_m is not None:
        result["estimatedDistanceInMeters"] = workout.estimated_distance_m
    if workout.description is not None:
        result["description"] = workout.description
    return result


# --- Upload -----------------------------------------------------------------


def upload_and_schedule(
    workout: Workout | dict,
    date_str: str | None = None,
    *,
    client=None,
    dry_run: bool = False,
) -> dict | None:
    """Lädt das Workout hoch und plant es optional ein.

    `client` muss `upload_workout(dict)`, `schedule_workout(id, date)` haben
    (z. B. ein konfigurierter `garminconnect.Garmin`-Client).

    Rückgabe (außer bei `dry_run`):
        {"workout_id": int, "scheduled_workout_id": int | None, "raw": <upload result>}
    """
    payload = workout if isinstance(workout, dict) else to_garmin_dict(workout)

    if dry_run:
        print("=== DRY RUN – kein Upload ===")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return None

    if client is None:
        raise ValueError("client erforderlich (oder dry_run=True)")

    result = client.upload_workout(payload)
    workout_id = result.get("workoutId")
    print(f"Upload OK – workout_id: {workout_id}  name: {payload['workoutName']}")

    scheduled_workout_id: int | None = None
    if date_str:
        sched = client.schedule_workout(workout_id, date_str)
        scheduled_workout_id = sched.get("workoutScheduleId")
        print(f"Geplant für {date_str} (scheduleId: {scheduled_workout_id})")

    return {
        "workout_id": workout_id,
        "scheduled_workout_id": scheduled_workout_id,
        "raw": result,
    }


def delete_uploaded(
    workout_id: int,
    scheduled_workout_id: int | None = None,
    *,
    client,
) -> None:
    """Entfernt erst den Schedule (falls vorhanden), dann das Workout-Template.

    Reihenfolge zählt: Garmin lehnt das Löschen eines noch geplanten Workouts ggf. ab.
    """
    if client is None:
        raise ValueError("client erforderlich")

    if scheduled_workout_id is not None:
        unschedule = next(
            (
                getattr(client, name)
                for name in _UNSCHEDULE_METHOD_CANDIDATES
                if callable(getattr(client, name, None))
            ),
            None,
        )
        if unschedule is None:
            raise AttributeError(
                "Garmin-Client bietet keine bekannte Unschedule-Methode "
                f"(probiert: {', '.join(_UNSCHEDULE_METHOD_CANDIDATES)}). "
                "garminconnect-Version prüfen."
            )
        unschedule(scheduled_workout_id)
        print(f"Unschedule OK – scheduled_workout_id: {scheduled_workout_id}")

    client.delete_workout(workout_id)
    print(f"Delete OK – workout_id: {workout_id}")
