"""Data types commonly used around this package"""

from pathlib import Path
from typing import Dict, Literal, Tuple, Union


CsvRow = list[str]
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
RawPointsLike = list[Union[TraceId, Timepoint, float]]
FullLayerData = Tuple[RawPointsLike, LayerParams, LayerTypeName]
