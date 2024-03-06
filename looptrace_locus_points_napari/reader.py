"""The main functionality of this napari plugin"""

from enum import Enum
import json
import os
from pathlib import Path
from typing import *


__author__ = "Vince Reuter"
__credits__ = ["Vince Reuter"]

LayerTypeName = Literal["points"]
FullLayerData = Tuple[List["Point"], Dict, LayerTypeName]
PathLike = Union[str, Path]
Point = List[float]

QC_FAIL_CODES_KEY = "failCodes"


def read_point_table_file(path: PathLike) -> FullLayerData:
    """
    Parse table of points data, using filepath to infer QC status to determine visual parameters.

    Specifically, this function is this package's main "contribution" in the terms 
    of the napari plugins language. It's a reader for a JSON file that represents on-disk 
    storage of a napari Points layer.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the JSON file to parse

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
    static_meta = {"size": 0.5, "edge_width": 0.1, "edge_width_is_relative": True, "n_dimensional": False}
    qc = QCStatus.from_path(path)
    dynamic_meta = {"edge_color": qc.color, "face_color": qc.color, "symbol": qc.shape}
    with open(path, 'r') as fh:
        records = json.load(fh)
    if qc == QCStatus.FAIL:
        dynamic_meta["text"] = QC_FAIL_CODES_KEY
        dynamic_meta["properties"] = {QC_FAIL_CODES_KEY: [r[QC_FAIL_CODES_KEY] for r in records]}
    return [[r["traceId"], r["time"], r["z"], r["y"], r["x"]] for r in records], {**static_meta, **dynamic_meta}, "points"


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


class QCStatus(Enum):
    """The possible QC status values; for the moment just pass/fail"""
    PASS = "pass"
    FAIL = "fail"

    @property
    def color(self) -> str:
        """Use red for QC pass, blue for QC fail."""
        if self is QCStatus.PASS:
            return "red"
        elif self is QCStatus.FAIL:
            return "blue"
        else:
            QCStatus.raise_match_error(self)

    @property
    def colour(self) -> str:
        """Alias for :py:method:`color`"""
        return self.color
    
    @property
    def shape(self) -> str:
        """Alias for :py:method:`symbol`"""
        return self.symbol

    @property
    def symbol(self) -> str:
        """Use star for QC pass, circle for QC fail."""
        if self is QCStatus.PASS:
            return "*"
        elif self is QCStatus.FAIL:
            return "o"
        else:
            QCStatus.raise_match_error(self)


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
    
    @classmethod
    def from_path(cls, p: PathLike) -> Optional["QCStatus"]:
        """Try to infer QC status from the suffix of the given path."""
        base, ext = os.path.splitext(os.path.basename(p))
        if ext == ".json":
            return QCStatus.from_string(base.split(".")[-1])
    
    @staticmethod
    def raise_match_error(obj: Any) -> NoReturn:
        """When QC status inference is attempted for a value for which it's not possible, raise this error."""
        raise ValueError(f"Not a recognised QC status (type {type(obj).__name__}): {obj}")
