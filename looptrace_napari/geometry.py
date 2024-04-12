"""Geometric types and tools"""

from abc import abstractmethod
from dataclasses import dataclass
from typing import Protocol

from numpydoc_decorator import doc


class LocatableXY(Protocol):
    
    @property
    @abstractmethod
    def x_coordinate(self) -> float:
        raise NotImplementedError

    @property
    @abstractmethod
    def y_coordinate(self) -> float:
        raise NotImplementedError


@dataclass(kw_only=True, frozen=True)
class ImagePoint2D(LocatableXY):
    x: float
    y: float

    def __post_init__(self) -> None:
        if not all(isinstance(c, float) for c in [self.x, self.y]):
            raise TypeError(f"At least one coordinate isn't floating-point! {self}")
        if any(c < 0 for c in [self.x, self.y]):
            raise ValueError(f"At least one coordinate is negative! {self}")
        
    def x_coordinate(self) -> float:
        return self.x
    
    def y_coordinate(self) -> float:
        return self.y
