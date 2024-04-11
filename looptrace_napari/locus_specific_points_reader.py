"""The main functionality of this napari plugin"""

import csv
import logging
import os
from pathlib import Path
from typing import (
    Callable, 
    Literal,
    Optional,
    Tuple, 
    Union,
)

from ._types import (
    CsvRow, 
    FullLayerData, 
    LayerParams,
    PathLike, 
    PointRecord,
    RawPointsLike,
    Timepoint,
    TraceId,
    )

__author__ = "Vince Reuter"
__credits__ = ["Vince Reuter"]

QC_FAIL_CODES_KEY = "failCodes"
QCCode = Literal[0, 1]


def get_reader(path: Union[PathLike, list[PathLike]]) -> Optional[Callable[[PathLike], list[FullLayerData]]]:
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
    static_params = {"size": 0.5, "edge_width": 0.05, "edge_width_is_relative": True, "n_dimensional": False}

    if isinstance(path, (str, Path)):
        base, ext = os.path.splitext(os.path.basename(path))
        if ext == ".csv":
            status_name = base.lower().split(".")[-1].lstrip("qc_").lstrip("qc")
            if status_name in {"pass", "passed"}:
                logging.debug(f"Parsing as QC-pass: {path}")
                color = "red"
                symbol = "*"
                read_rows = parse_passed
            elif status_name in {"fail", "failed"}:
                logging.debug(f"Parsing as QC-fail: {path}")
                color = "blue"
                symbol = "o"
                read_rows = parse_failed
            else:
                logging.warning(f"Could not infer QC status from '{status_name}', from path {path}")
                return None
            base_meta = {"edge_color": color, "face_color": color, "symbol": symbol}
            def parse(p):
                with open(p, mode='r', newline='') as fh:
                    rows = list(csv.reader(fh))
                data, extra_meta = read_rows(rows)
                params = {**static_params, **base_meta, **extra_meta}
                return data, params, "points"
            return lambda p: [parse(p)]
        else:
            logging.debug(f"Not a CSV: {path}")
            return None
    else:
        logging.debug(f"Not a path-like: {path}")
        return None
            


def parse_passed(rows: list[CsvRow]) -> Tuple[RawPointsLike, LayerParams]:
    return [parse_simple_record(r, exp_len=5) for r in rows], {}


def parse_failed(rows: list[CsvRow]) -> Tuple[RawPointsLike, LayerParams]:
    if not rows:
        data = []
        codes = []
    else:
        data_codes_pairs: list[Tuple[PointRecord, QCCode]] = [(parse_simple_record(r, exp_len=6), r[5]) for r in rows]
        data, codes = map(list, zip(*data_codes_pairs))
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
    return [trace, timepoint, z, y, x]
