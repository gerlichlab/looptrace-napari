"""The main functionality of this napari plugin"""

from abc import ABC, abstractmethod
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
FullLayerData = Tuple[List[Union[TraceId, Timepoint, float]], LayerParams, LayerTypeName]

QC_FAIL_CODES_KEY = "failCodes"


def read_point_table_file(path: PathLike) -> FullLayerData:
    """
    Parse table of points data, using filepath to infer QC status to determine visual parameters.

    Specifically, this function is this package's main "contribution" in the terms 
    of the napari plugins language. It's a reader for a CSV file that represents on-disk 
    storage of a napari Points layer.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the CSV file to parse

    Returns
    -------
    pd.DataFrame, Dict, LayerTypeName
        A tuple in which the first element defines the axes and points that will 
        be shown in `napari`, the second element is keyword arguments for the points 
        layer constructor, and the third element is the name for the type of layer

    Raises
    ------
    ValueError: if the given path doesn't yield a QCStatus inference that's known; 
        this should never happen, because this function's application should be restricted 
        (by virtue of filtration by the plugin hook and/or by the package's accepted 
        filename patterns) to cases when the `QCstatus` can indeed be inferred from the `path`.

    See Also
    --------
    :py:class:`QCStatus`
    """
    static_params = {"size": 0.5, "edge_width": 0.1, "edge_width_is_relative": True, "n_dimensional": False}
    qc = QCStatus.from_path(path)
    with open(path, mode='r', newline='') as fh:
        rows: List[CsvRow] = list(csv.reader(fh))
    data, status_dependent_params = qc.get_data_and_params_for_napari_layer(rows)
    return data, {**static_params, **status_dependent_params}, "points"


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

    See Also
    --------
    :py:func:`read_point_table_file`
    """
    if isinstance(path, (str, Path)) and QCStatus.from_path(path) is not None:
        return lambda p: [read_point_table_file(p)]


class QCStatus(ABC):
    """The possible QC status values; for the moment just pass/fail"""

    @abstractmethod
    def get_data_and_params_for_napari_layer(rows: List[CsvRow]) -> Tuple[List[PointRecord], LayerParams]:
        raise NotImplementedError("get_data_and_params must be implemented in concrete subclass of QCStatus!")

    @property
    @abstractmethod
    def is_pass(self) -> bool:
        raise NotImplementedError("is_pass must be implemented in concrete subclass of QCStatus!")

    @property
    def is_fail(self) -> bool:
        return not self.is_pass
    
    @property
    def _base_dynamic_metadata(self) -> LayerParams:
        return {"edge_color": self.color, "face_color": self.color, "symbol": self.symbol}

    @property
    def color(self) -> str:
        """Use red for QC pass, blue for QC fail."""
        if self.is_pass:
            return "red"
        if self.is_fail:
            return "blue"
        QCStatus.raise_match_error(self)

    @property
    def colour(self) -> str:
        """Alias for :py:method:`color`"""
        return self.color
    
    @property
    def symbol(self) -> str:
        """Use star for QC pass, circle for QC fail."""
        if self.is_pass:
            return "*"
        if self.is_fail:
            return "o"
        QCStatus.raise_match_error(self)

    @classmethod
    def from_path(cls, p: PathLike) -> Optional["QCStatus"]:
        """Try to infer QC status from the suffix of the given path."""
        base, ext = os.path.splitext(os.path.basename(p))
        if ext == ".csv":
            return QCStatus.from_string(base.split(".")[-1])
    
    @classmethod
    def from_string(cls, s: str) -> Optional["QCStatus"]:
        """Try to parse the given text as a QC status."""
        s = s.lower()
        s = s.lstrip("qc_").lstrip("qc")
        if s in {"pass", "passed"}:
            return cls.PASS
        elif s in {"fail", "failed"}:
            return cls.FAIL
        return None
    
    @staticmethod
    def raise_match_error(obj: Any) -> NoReturn:
        """When QC status inference is attempted for a value for which it's not possible, raise this error."""
        raise ValueError(f"Not a recognised QC status (type {type(obj).__name__}): {obj}")


class QCPass(QCStatus):
    
    @property
    def is_pass(self) -> bool:
        return True

    def get_data_and_params_for_napari_layer(self, rows: List[CsvRow]) -> Tuple[List[PointRecord], LayerParams]:
        return [parse_simple_record(r, exp_len=5) for r in rows], self._base_dynamic_metadata
    

class QCFail(QCStatus):

    @property
    def is_pass(self) -> bool:
        return False
    
    def get_data_and_params_for_napari_layer(self, rows: List[CsvRow]) -> Tuple[List[PointRecord], LayerParams]:
        data_code_pairs = [(parse_simple_record(r, exp_len=6), r[5]) for r in rows]
        try:
            data, codes = zip(*data_code_pairs)
        except:
            data, codes = [], []
        extra_params = {"text": QC_FAIL_CODES_KEY, "properties": {QC_FAIL_CODES_KEY: codes}}
        return data, {**self._base_dynamic_metadata **extra_params}


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
