"""Reading locus-specific spots and points data from looptrace for visualisation in napari"""

import csv
import dataclasses
import logging
import os
from enum import Enum
from math import floor
from pathlib import Path
from typing import Callable, Dict, Literal, Optional, Tuple, Union

import numpy as np
from numpydoc_decorator import doc  # type: ignore[import-untyped]

from ._colors import DEEP_SKY_BLUE, GOLDENROD
from ._docs import CommonReaderDoc
from .geometry import ImagePoint3D, LocatableXY, LocatableZ, ZCoordinate
from .types import CsvRow, LayerParams, PathLike
from .types import TimepointFrom0 as Timepoint  # pylint: disable=unused-import
from .types import TraceIdFrom0 as TraceId

__author__ = "Vince Reuter"
__credits__ = ["Vince Reuter"]

FlatPointRecord = list[Union[float, ZCoordinate]]
FullLayerData = Tuple[list[FlatPointRecord], "LayerParams", "LayerTypeName"]
LayerTypeName = Literal["points"]
QCFailReasons = str


@doc(
    summary=(
        "This is the main hook required by napari / napari plugins to provide a Reader"
        " plugin."
    ),
    returns=CommonReaderDoc.returns,
    notes=CommonReaderDoc.notes,
)
def get_reader(
    path: CommonReaderDoc.path_type,
) -> Optional[Callable[[PathLike], list[FullLayerData]]]:
    static_params = {
        "edge_width": 0.1,
        "edge_width_is_relative": True,
        "n_dimensional": False,
    }

    def do_not_parse(why: str, *, level: int = logging.DEBUG) -> None:
        return logging.log(
            level=level,
            msg=f"{why}, cannot be read as looptrace locus-specific points: {path}",
        )

    # Input should be a single extant filepath.
    if not isinstance(path, (str, Path)):
        return do_not_parse("Not a path-like")  # type: ignore[func-returns-value]
    if not os.path.isfile(path):
        return do_not_parse("Not an extant file")  # type: ignore[func-returns-value]

    # Input should also be a CSV.
    base, ext = os.path.splitext(os.path.basename(path))
    if ext != ".csv":
        return do_not_parse("Not a CSV")  # type: ignore[func-returns-value]

    # Determine how to read and display the points layer to be parsed.
    status_name = base.lower().split(".")[-1].lstrip("qc_").lstrip("qc")
    if status_name in {"pass", "passed"}:
        logging.debug("Will parse sas QC-pass: %s", path)
        color = GOLDENROD
        read_rows = parse_passed
    elif status_name in {"fail", "failed"}:
        logging.debug("Will parse as QC-fail: %s", path)
        color = DEEP_SKY_BLUE
        read_rows = parse_failed
    else:
        return do_not_parse(  # type: ignore[func-returns-value]
            f"Could not infer QC status from '{status_name}'", level=logging.WARNING
        )
    base_meta = {"edge_color": color, "face_color": color}

    # Build the actual parser function.
    def parse(p):
        with open(p, mode="r", newline="") as fh:
            rows = list(csv.reader(fh))
        point_records, center_flags, extra_meta = read_rows(rows)
        if not point_records:
            logging.warning("No data rows parsed!")
        shape_meta = {
            "symbol": ["*" if is_center else "o" for is_center in center_flags],
        }
        params = {**static_params, **base_meta, **extra_meta, **shape_meta}
        return [pt_rec.flatten() for pt_rec in point_records], params, "points"

    return lambda p: [parse(p)]


@doc(
    summary="Parse records from points which passed QC.",
    parameters=dict(rows="Records to parse"),
    returns="""
        A pair in which the first element is the array-like of points coordinates, 
        and the second element is the mapping from attribute name to list of values (1 per point).
    """,
    notes="https://napari.org/stable/plugins/guides.html#layer-data-tuples",
)
def parse_passed(
    rows: list[CsvRow],
) -> Tuple[list["PointRecord"], list[bool], LayerParams]:
    records = [parse_simple_record(r, exp_num_fields=5) for r in rows]
    max_z = max(r.get_z_coordinate() for r in records)
    points: list["PointRecord"] = []
    center_flags: list[bool] = []
    for rec in records:
        new_points, new_flags = expand_along_z(rec, z_max=max_z)
        points.extend(new_points)
        center_flags.extend(new_flags)
    sizes = [1.5 if is_center else 1.0 for is_center in center_flags]
    return points, center_flags, {"size": sizes}


@doc(
    summary="Parse records from points which failed QC.",
    parameters=dict(rows="Records to parse"),
    returns="""
        A pair in which the first element is the array-like of points coordinates, 
        and the second element is the mapping from attribute name to list of values (1 per point).
    """,
    notes="https://napari.org/stable/plugins/guides.html#layer-data-tuples",
)
def parse_failed(
    rows: list[CsvRow],
) -> Tuple[list["PointRecord"], list[bool], LayerParams]:
    record_qc_pairs: list[Tuple[PointRecord, QCFailReasons]] = []
    for row in rows:
        try:
            qc = row[InputFileColumn.QC.get]
            rec = parse_simple_record(row, exp_num_fields=6)
        except IndexError:
            logging.error("Bad row: %s", row)
            raise
        record_qc_pairs.append((rec, qc))
    max_z = max(r.get_z_coordinate() for r, _ in record_qc_pairs)
    points: list["PointRecord"] = []
    center_flags: list[bool] = []
    codes: list[QCFailReasons] = []
    for rec, qc in record_qc_pairs:
        new_points, new_flags = expand_along_z(rec, z_max=max_z)
        points.extend(new_points)
        center_flags.extend(new_flags)
        codes.extend([qc] * len(new_points))
    params = {
        "size": 0,  # Make the point invisible and just use text.
        "text": {
            "string": "{failCodes}",
            "color": DEEP_SKY_BLUE,
        },
        "properties": {"failCodes": codes},
    }
    return points, center_flags, params


@doc(
    summary="Parse single-point from a single record (e.g., row from a CSV file).",
    parameters=dict(
        r="Record (e.g. CSV row) to parse",
        exp_num_fields=(
            "The expected number of data fields (e.g., columns) in the record"
        ),
    ),
    returns="""
        A pair of values in which the first element represents a locus spot's trace ID and timepoint, 
        and the second element represents the (z, y, x) coordinates of the centroid of the spot fit.
    """,
)
def parse_simple_record(r: CsvRow, *, exp_num_fields: int) -> "PointRecord":
    """Parse a single line from an input CSV file."""
    if not isinstance(r, list):
        raise TypeError(f"Record to parse must be list, not {type(r).__name__}")
    if len(r) != exp_num_fields:
        raise ValueError(
            f"Expected record of length {exp_num_fields} but got {len(r)}: {r}"
        )
    trace = TraceId(int(r[InputFileColumn.TRACE.get]))
    timepoint = Timepoint(int(r[InputFileColumn.TIMEPOINT.get]))
    z = float(r[InputFileColumn.Z.get])
    y = float(r[InputFileColumn.Y.get])
    x = float(r[InputFileColumn.X.get])
    point = ImagePoint3D(z=z, y=y, x=x)
    return PointRecord(trace_id=trace, timepoint=timepoint, point=point)


@dataclasses.dataclass(frozen=True, kw_only=True)
class PointRecord(LocatableXY, LocatableZ):
    trace_id: TraceId
    timepoint: Timepoint
    point: ImagePoint3D

    def __post_init__(self) -> None:
        bads: Dict[str, object] = {}
        if not isinstance(self.trace_id, TraceId):
            bads["trace ID"] = self.trace_id
        if not isinstance(self.timepoint, Timepoint):
            bads["timepoint"] = self.timepoint
        if not isinstance(self.point, ImagePoint3D):
            bads["point"] = self.point
        if bads:
            messages = "; ".join(
                f"Bad type ({type(v).__name__}) for {k}" for k, v in bads.items()
            )
            raise TypeError(f"Cannot create point record: {messages}")

    @doc(summary="Flatten")
    def flatten(self) -> FlatPointRecord:
        return [
            self.trace_id.get,
            self.timepoint.get,
            self.get_z_coordinate(),
            self.get_y_coordinate(),
            self.get_x_coordinate(),
        ]

    def get_x_coordinate(self) -> float:
        return self.point.x

    def get_y_coordinate(self) -> float:
        return self.point.y

    def get_z_coordinate(self) -> ZCoordinate:
        return self.point.z

    @doc(summary="Round point position to nearest z-slice")
    def with_truncated_z(self) -> "PointRecord":
        return self.with_new_z(floor(self.get_z_coordinate()))

    @doc(
        summary="Replace this instance's point with a copy with updated z.",
        parameters=dict(z="New z-coordinate value"),
    )
    def with_new_z(self, z: int) -> "PointRecord":
        pt = ImagePoint3D(x=self.point.x, y=self.point.y, z=z)
        return dataclasses.replace(self, point=pt)


@doc(
    summary="Create ancillary points from main point",
    parameters=dict(
        r="The record to expand along z-axis",
        z_max="The maximum z-coordinate",
    ),
)
def expand_along_z(
    r: PointRecord, *, z_max: Union[float, np.float64]
) -> Tuple[list[PointRecord], list[bool]]:
    if not isinstance(z_max, (int, float, np.float64)):
        raise TypeError(f"Bad type for z_max: {type(z_max).__name__}")

    r = r.with_truncated_z()  # type: ignore[no-redef]
    z_center = int(r.get_z_coordinate())
    z_max = int(floor(z_max))  # type: ignore[no-redef]
    assert isinstance(z_center, int) and isinstance(z_max, int), (
        f"Z center and Z max must be int; got {type(z_center).__name__} and"
        f" {type(z_max).__name__}"
    )

    # Check that max z and center z make sense together.
    if z_max < z_center:
        raise ValueError(f"Max z must be at least as great as central z ({z_center})")

    # Build the records and flags of where the center in z really is.
    predecessors = [(r.with_new_z(i), False) for i in range(z_center)]
    successors = [(r.with_new_z(i), False) for i in range(z_center + 1, z_max + 1)]
    points, params = zip(*(predecessors + [(r, True)] + successors))

    # Each record should give rise to a total of 1 + z_max records, since numbering from 0.
    assert (
        len(points) == 1 + z_max
    ), f"Point={r}, z_max={z_max}, len(points)={len(points)}"
    return points, params  # type: ignore[return-value]


class InputFileColumn(Enum):
    """Indices of the different columns to parse as particular fields"""

    TRACE = 0
    TIMEPOINT = 1
    Z = 2
    Y = 3
    X = 4
    QC = 5

    @property
    def get(self) -> int:
        return self.value
