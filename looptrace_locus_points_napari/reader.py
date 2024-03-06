"""The main functionality of this napari plugin"""

import csv
import os
from pathlib import Path
from typing import *
from typing import List, Tuple

__author__ = "Vince Reuter"
__credits__ = ["Vince Reuter"]

CsvRow = List[str]
PathLike = Union[str, Path]
LayerTypeName = Literal["points"]
LayerParams = Dict
TraceId = int
Timepoint = int
PointId = Tuple[TraceId, Timepoint]
Point3D = Tuple[float, float, float]
FailCodesText = str
PointRecord = Tuple[PointId, Point3D]
QCPassRecord = PointRecord
QCFailRecord = Tuple[PointId, Point3D, FailCodesText]
RawDataLike = List[Union[TraceId, Timepoint, float]]
FullLayerData = Tuple[RawDataLike, LayerParams, LayerTypeName]

QC_FAIL_CODES_KEY = "failCodes"


def get_reader(path: Union[PathLike, List[PathLike]]) -> Optional[Callable[[PathLike], List[FullLayerData]]]:
    """
    This is the main hook required by napari / napari plugins to provide a Reader plugin.

    Parameters
    ----------
    path : str or pathlib.Path or list of str or pathlib.Path

    Returns
    -------
    If the plugin represented by this package is intended to read a file of the given type (inferred from 
    the file's extension), then the function with which to parse that file. Otherwise, nothing.
    """
    static_params = {"size": 0.5, "edge_width": 0.1, "edge_width_is_relative": True, "n_dimensional": False}

    if isinstance(path, (str, Path)):
        base, ext = os.path.splitext(os.path.basename(p))
        if ext == ".csv":
            status_name = base.lower().lstrip("qc_").lstrip("qc")
            if status_name in {"pass", "passed"}:
                color = "red"
                symbol = "*"
                read_rows = parse_passed
            elif status_name in {"fail", "failed"}:
                color = "blue"
                symbol = "o"
                read_rows = parse_passed
            else:
                return None
            base_meta = {"edge_color": color, "face_color": color, "symbol": symbol}
            def parse(p):
                with open(p, mode='r', newline='') as fh:
                    rows = list(csv.reader(fh))
                data, extra_meta = read_rows(rows)
                return data, {**static_params, **base_meta, **extra_meta}
            return lambda p: [parse(p)]


def parse_passed(rows: List[CsvRow]) -> Tuple[RawDataLike, LayerParams]:
    return [parse_simple_record(r, exp_len=5) for r in rows], {}


def parse_failed(rows: List[CsvRow]) -> Tuple[RawDataLike, LayerParams]:
    data_codes_pairs = [(parse_simple_record(r, exp_len=6), r[5]) for r in rows]
    try:
        data, codes = zip(*data_codes_pairs)
    except:
        data, codes = [], []
    return data, {"text": QC_FAIL_CODES_KEY, "properties": {QC_FAIL_CODES_KEY: codes}}


def parse_simple_record(r: CsvRow, *, exp_len: int) -> PointRecord:
    """Parse a single line from an input CSV file."""
    if not isinstance(r, list):
        raise TypeError(f"Record to parse must be list, not {type(r).__name__}")
    if len(r) != exp_len:
        raise ValueError(f"Expected record of length {exp_len} but got {len(r)}: {r}")
    trace: TraceId = int(r[0])
    timepoint: Timepoint = int(r[1])
    z = float(r[2])
    y = float(r[3])
    x = float(r[4])
    return (trace, timepoint), (z, y, x)
