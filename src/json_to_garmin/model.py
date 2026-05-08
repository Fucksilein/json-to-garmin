"""Generisches Workout-Modell — Step-Baum mit Targets.

Sport-agnostisch. Die Garmin-spezifische Übersetzung lebt in `garmin_api.py`.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

Sport = Literal["bike", "run", "swim", "strength", "other"]
StepKind = Literal["warmup", "work", "recover", "rest", "cooldown", "other"]
EndCondition = Literal["time", "distance", "lap_button", "calories"]
TargetKind = Literal[
    "none", "power", "power_zone", "hr_zone", "pace", "cadence", "speed"
]


class Target(BaseModel):
    """Step-Target.

    - `power`        : low/high in Watt (absolut)
    - `power_zone`   : zone 1-7
    - `hr_zone`      : zone 1-5
    - `pace`         : low/high als "M:SS" pro km (low = schneller, high = langsamer)
    - `cadence`      : low/high in rpm bzw. spm
    - `speed`        : low/high in m/s
    - `none`         : kein Target
    """

    model_config = ConfigDict(extra="forbid")

    kind: TargetKind = "none"
    low: float | None = None
    high: float | None = None
    pace_low: str | None = None
    pace_high: str | None = None
    zone: int | None = None


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["step"] = "step"
    kind: StepKind
    end: EndCondition
    value: float | None = None  # secs / meters / kcal — None nur bei lap_button
    target: Target = Field(default_factory=lambda: Target(kind="none"))
    note: str | None = None


class Repeat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["repeat"] = "repeat"
    iterations: int = Field(ge=1)
    steps: list[StepOrRepeat]
    skip_last_rest: bool = True


StepOrRepeat = Annotated[Union[Step, Repeat], Field(discriminator="type")]
Repeat.model_rebuild()


class Workout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    sport: Sport
    steps: list[StepOrRepeat]
    estimated_duration_sec: int | None = None
    estimated_distance_m: float | None = None
    description: str | None = None
