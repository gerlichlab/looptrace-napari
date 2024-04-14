"""Geometric types and tools"""

from abc import abstractmethod
from dataclasses import dataclass
from typing import Protocol

from numpydoc_decorator import doc  # type: ignore[import-untyped]

# TODO: need Python >= 3.12
# See: https://github.com/gerlichlab/looptrace-napari/issues/6
# from typing import override


class LocatableXY(Protocol):
    """Something that admits x- and y-coordinate."""

    @abstractmethod
    def get_x_coordinate(self) -> float:
        raise NotImplementedError

    @abstractmethod
    def get_y_coordinate(self) -> float:
        raise NotImplementedError


@doc(
    summary="Bundle x and y position to create point in 2D space.",
    parameters=dict(
        x="Position in x",
        y="Position in y",
    ),
)
@dataclass(kw_only=True, frozen=True)
class ImagePoint2D(LocatableXY):
    x: float
    y: float

    def __post_init__(self) -> None:
        if not all(isinstance(c, float) for c in [self.x, self.y]):
            raise TypeError(f"At least one coordinate isn't floating-point! {self}")
        if any(c < 0 for c in [self.x, self.y]):
            raise ValueError(f"At least one coordinate is negative! {self}")

    # TODO: adopt @override once on Python >= 3.12
    # See: https://github.com/gerlichlab/looptrace-napari/issues/6
    def get_x_coordinate(self) -> float:
        return self.x

    # TODO: adopt @override once on Python >= 3.12
    # See: https://github.com/gerlichlab/looptrace-napari/issues/6
    # @override
    def get_y_coordinate(self) -> float:
        return self.y
