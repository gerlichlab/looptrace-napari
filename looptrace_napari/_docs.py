"""Documentation-related helpers"""

from dataclasses import dataclass

from typing_extensions import Annotated

from .types import PathOrPaths


@dataclass(frozen=True, kw_only=True)
class CommonReaderDoc:
    path_type = Annotated[
        PathOrPaths,
        "The file(s) or folder(s) for which to attempt to infer reader function",
    ]
    returns = "A None if we can't read the given path(s), else a reader function"
    notes = "https://napari.org/stable/plugins/guides.html#layer-data-tuples"
