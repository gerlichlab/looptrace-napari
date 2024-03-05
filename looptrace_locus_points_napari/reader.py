"""The main functionality of this napari plugin"""

from enum import Enum
import os
from pathlib import Path
from typing import *

import pandas as pd

__author__ = "Vince Reuter"
__credits__ = ["Vince Reuter"]

LayerTypeName = Literal["points"]
FullLayerData = Tuple[pd.DataFrame, Dict, LayerTypeName]
PathLike = Union[str, Path]


def read_point_table_file(path: PathLike) -> FullLayerData:
    """
    Parse the table of points data.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the CSV file to parse

    Returns
    -------
    pd.DataFrame, Dict, LayerTypeName
        A tuple in which the first element defines the axes and points that will 
        be shown in `napari`, the second is keyword arguments for the points 
        layer constructor, and the third is the name for the type of layer

    Raises
    ------
    ValueError: if the given path doesn't yield a QCStatus inference that's known

    See Also
    --------
    :py:class:`reader.QCStatus`
    """
    point_table = pd.read_csv(path)
    points = point_table[[f"axis-{i}" for i in range(5)]]
    static_meta = {"size": 0.5, "edge_width": 0.1, "edge_width_is_relative": True, "n_dimensional": False}
    qc = QCStatus.from_path(path)
    dynamic_meta = {"edge_color": qc.color, "face_color": qc.color, "symbol": qc.shape}
    meta = {**static_meta, **dynamic_meta}
    return points, meta, "points"


def get_reader(path: Union[PathLike, List[PathLike]]) -> Optional[Callable[[PathLike], List[FullLayerData]]]:
    if isinstance(path, (str, Path)) and QCStatus.from_path(path) is not None:
        return lambda p: [read_point_table_file(p)]


class QCStatus(Enum):
    """The possible QC status values"""
    PASS = "pass"
    FAIL = "fail"

    @property
    def color(self) -> str:
        if self is QCStatus.PASS:
            return "red"
        elif self is QCStatus.FAIL:
            return "blue"
        else:
            QCStatus.raise_match_error(self)

    @property
    def colour(self) -> str:
        return self.color
    
    @property
    def shape(self) -> str:
        return self.symbol

    @property
    def symbol(self) -> str:
        if self is QCStatus.PASS:
            return "*"
        elif self is QCStatus.FAIL:
            return "o"
        else:
            QCStatus.raise_match_error(self)


    @classmethod
    def from_string(cls, s: str) -> Optional["QCStatus"]:
        s = s.lower()
        s = s.lstrip("qc_").lstrip("qc")
        if s in {"pass", "passed"}:
            return cls.PASS
        elif s in {"fail", "failed"}:
            return cls.FAIL
        return None
    
    @classmethod
    def from_path(cls, p: PathLike) -> Optional["QCStatus"]:
        base, ext = os.path.splitext(os.path.basename(p))
        if ext == ".csv":
            return QCStatus.from_string(base.split(".")[-1])
    
    @staticmethod
    def raise_match_error(obj: Any) -> NoReturn:
        raise ValueError(f"Not a recognised QC status (type {type(obj).__name__}): {obj}")
