"""Reading locus-specific spots and points data from looptrace for visualisation in napari"""

import csv
import logging
import os
from pathlib import Path
from typing import Callable, Literal, Optional, Tuple, Union

from numpydoc_decorator import doc  # type: ignore[import-untyped]

from ._docs import CommonReaderDoc
from .types import (  # pylint: disable=unused-import
    CsvRow,
    LayerParams,
    PathLike,
    PointRecord,
    Timepoint,
    TraceId,
)

__author__ = "Vince Reuter"
__credits__ = ["Vince Reuter"]

FullLayerData = Tuple["RawLocusPointsLike", "LayerParams", "LayerTypeName"]
LayerTypeName = Literal["points"]
QCFailReasons = str
RawLocusPointsLike = list[Union["TraceId", "Timepoint", float]]

QC_FAIL_CODES_KEY = "failCodes"


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
        "size": 0.5,
        "edge_width": 0.05,
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
        logging.debug("Parsing as QC-pass: %s", path)
        color = "red"
        symbol = "*"
        read_rows = parse_passed
    elif status_name in {"fail", "failed"}:
        logging.debug("Parsing as QC-fail: %s", path)
        color = "blue"
        symbol = "o"
        read_rows = parse_failed
    else:
        return do_not_parse(  # type: ignore[func-returns-value]
            f"Could not infer QC status from '{status_name}'", level=logging.WARNING
        )

    # Build the actual parser function.
    base_meta = {"edge_color": color, "face_color": color, "symbol": symbol}

    def parse(p):
        with open(p, mode="r", newline="") as fh:
            rows = list(csv.reader(fh))
        data, extra_meta = read_rows(rows)
        if not data:
            logging.warning("No data rows parsed!")
        params = {**static_params, **base_meta, **extra_meta}
        return data, params, "points"

    return lambda p: [parse(p)]


@doc(
    summary="Parse records from points which passed QC.",
    parameters=dict(records="Records to parse"),
    returns="""
        A pair in which the first element is the array-like of points coordinates, 
        and the second element is the mapping from attribute name to list of values (1 per point).
    """,
    notes="https://napari.org/stable/plugins/guides.html#layer-data-tuples",
)
def parse_passed(records: list[CsvRow]) -> Tuple[RawLocusPointsLike, LayerParams]:
    return [parse_simple_record(r, exp_num_fields=5) for r in records], {}


@doc(
    summary="Parse records from points which failed QC.",
    parameters=dict(records="Records to parse"),
    returns="""
        A pair in which the first element is the array-like of points coordinates, 
        and the second element is the mapping from attribute name to list of values (1 per point).
    """,
    notes="https://napari.org/stable/plugins/guides.html#layer-data-tuples",
)
def parse_failed(records: list[CsvRow]) -> Tuple[RawLocusPointsLike, LayerParams]:
    if not records:
        data = []
        codes = []
    else:
        data_codes_pairs: list[Tuple[PointRecord, QCFailReasons]] = [
            (parse_simple_record(r, exp_num_fields=6), r[5]) for r in records
        ]
        data, codes = map(list, zip(*data_codes_pairs))
    return data, {"text": QC_FAIL_CODES_KEY, "properties": {QC_FAIL_CODES_KEY: codes}}


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
def parse_simple_record(r: CsvRow, *, exp_num_fields: int) -> RawLocusPointsLike:
    """Parse a single line from an input CSV file."""
    if not isinstance(r, list):
        raise TypeError(f"Record to parse must be list, not {type(r).__name__}")
    if len(r) != exp_num_fields:
        raise ValueError(
            f"Expected record of length {exp_num_fields} but got {len(r)}: {r}"
        )
    trace = int(r[0])
    timepoint = int(r[1])
    z = float(r[2])
    y = float(r[3])
    x = float(r[4])
    return [trace, timepoint, z, y, x]
