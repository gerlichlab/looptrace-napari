"""Data types commonly used around this package"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, Union

from numpydoc_decorator import doc  # type: ignore[import-untyped]

CsvRow = list[str]
FailCodesText = str
LayerParams = Dict
PathLike = Union[str, Path]
PathOrPaths = Union[PathLike, list[PathLike]]
PointId = Tuple["TraceId", "Timepoint"]
PointRecord = Tuple[PointId, "Point3D"]
Point3D = Tuple[float, float, float]
QCFailRecord = Tuple[PointId, Point3D, FailCodesText]
QCPassRecord = PointRecord
TraceId = int
Timepoint = int


@doc(
    summary="Wrap an int as a 1-based field of view (FOV).",
    parameters=dict(get="The value to wrape"),
    raises=dict(
        TypeError="If the given value to wrap isn't an integer",
        ValueError="If the given value to wrap isn't positive",
    ),
)
@dataclass(frozen=True, order=True)
class FieldOfViewFrom1:
    get: int

    def __post_init__(self) -> None:
        _refine_as_pos_int(self.get, context="FOV")


@doc(
    summary="Wrap an int as a 1-based nucleus number.",
    parameters=dict(get="The value to wrap"),
    raises=dict(
        TypeError="If the given value to wrap isn't an integer",
        ValueError="If the given value to wrap isn't positive",
    ),
)
@dataclass(frozen=True, order=True)
class NucleusNumber:
    get: int

    def __post_init__(self) -> None:
        _refine_as_pos_int(self.get, context="nucleus number")


def _refine_as_pos_int(x: object, *, context: str) -> None:
    if not isinstance(x, int):
        raise TypeError(f"Non-integer as {context}! {x} (type {type(x).__name__})")
    if x < 1:
        raise ValueError(f"1-based {context} must be positive int, not {x}")
