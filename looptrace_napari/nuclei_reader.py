"""Reading looptrace-written, ZARR-stored data"""

import logging
import os
import warnings
from dataclasses import dataclass
from enum import Enum
from operator import itemgetter
from pathlib import Path
from typing import Dict, Literal, Mapping, Optional, Tuple, Union

import dask.array as da
import numpy as np
import numpy.typing as npt
import pandas as pd
import zarr  # type: ignore[import-untyped]
from numpydoc_decorator import doc  # type: ignore[import-untyped]

from ._docs import CommonReaderDoc
from .geometry import ImagePoint2D
from .types import FieldOfViewFrom1, LayerParams, NucleusNumber, PathLike

PixelValue = Union[np.uint8, np.uint16]
PixelArray = Union[npt.NDArray[PixelValue], da.Array]

# Generic ArrayLike since element type differs depending on kind of layer.
FullLayerData = Tuple[npt.ArrayLike, LayerParams, "LayerTypeName"]
# We'll produce one of each of these types of layers.
LayerTypeName = Union[Literal["image"], Literal["labels"], Literal["points"]]

# Specific layer types
ImageLayer = Tuple[npt.ArrayLike, LayerParams, Literal["image"]]
MasksLayer = Tuple[npt.ArrayLike, LayerParams, Literal["labels"]]
CentroidsLayer = Tuple[npt.ArrayLike, LayerParams, Literal["points"]]

# Environment variable for finding nuclei channel if needed.
LOOPTRACE_NAPARI_NUCLEI_CHANNEL_ENV_VAR = "LOOPTRACE_NAPARI_NUCLEI_CHANNEL"


@doc(
    summary=(
        "This is the main hook required by napari / napari plugins to provide a Reader"
        " plugin."
    ),
    returns=CommonReaderDoc.returns,
    notes=CommonReaderDoc.returns,
)
def get_reader(path: CommonReaderDoc.path_type):
    def do_not_parse(why: str, *, level: int = logging.DEBUG) -> None:
        return logging.log(
            level=level,
            msg=f"{why}, cannot read looptrace nuclei visualisation data: {path}",
        )

    # Input should be a single extant folder.
    if not isinstance(path, (str, Path)):
        return do_not_parse(f"Not a path-like: {path}")
    if not os.path.isdir(path):
        return do_not_parse(f"Not an extant directory: {path}")
    path: Path = Path(path)  # type: ignore[no-redef]

    # Each of the subpaths to parse must be extant folder.
    if not NucleiDataSubfolders.all_present_within(path):
        return do_not_parse(
            "At least one subpath to parse isn't a folder!"
            f" {NucleiDataSubfolders.relpaths(path)}."
        )

    return lambda root: build_layers(NucleiDataSubfolders.read_all_from_root(root))


class NucleiDataSubfolders(Enum):
    IMAGES = "nuc_images"
    MASKS = "nuc_masks"
    CENTERS = "_nuclear_masks_visualisation"

    @classmethod
    def all_present_within(cls, p: PathLike) -> bool:
        return all(m.is_present_within(p) for m in cls)

    @classmethod
    def read_all_from_root(
        cls, p: PathLike
    ) -> Dict[FieldOfViewFrom1, "NucleiVisualisationData"]:
        image_paths = find_paths_by_fov(cls.IMAGES.relpath(p), extension=".zarr")
        masks_paths = find_paths_by_fov(cls.MASKS.relpath(p), extension=".zarr")
        centers_paths = find_paths_by_fov(
            cls.CENTERS.relpath(p), extension=".nuclear_masks.csv"
        )
        fields_of_view = (
            set(image_paths.keys())
            & set(masks_paths.keys())
            & set(centers_paths.keys())
        )
        logging.debug("Image paths count: %d", len(image_paths))
        logging.debug("Masks paths count: %d", len(masks_paths))
        logging.debug("Centers paths count: %d", len(centers_paths))
        bundles: Dict[FieldOfViewFrom1, "NucleiVisualisationData"] = {}
        for fov in sorted(fields_of_view):
            logging.debug("Reading data for FOV: %d", fov.get)
            image_fp: Path = image_paths[fov]
            logging.debug("Reading nuclei image: %s", image_fp)
            image = _read_zarr(image_fp)
            masks_fp: Path = masks_paths[fov]
            logging.debug("Reading nuclei masks: %s", masks_fp)
            masks = _read_zarr(masks_fp)
            centers_fp: Path = centers_paths[fov]
            logging.debug("Reading nuclei centers: %s", centers_fp)
            centers = _read_csv(centers_fp)
            bundles[fov] = NucleiVisualisationData(
                image=image, masks=masks, centers=centers
            )
        return bundles

    @classmethod
    def relpaths(cls, p: PathLike) -> Dict[str, Path]:
        return {m.value: m.relpath(p) for m in cls}

    def is_present_within(self, p: PathLike) -> bool:
        return self.relpath(p).is_dir()

    def relpath(self, p: PathLike) -> Path:
        return Path(p) / self.value


@doc(
    summary="Bundle the data needed to visualise nuclei.",
    parameters=dict(
        image="The array of pixel values, e.g. of DAPI staining in a particular FOV",
        masks="""
            The array of region-defining label indicators which represent nuclei regions. 
            The values should be nonnegative integers, with 0 representing portions of the 
            image outside a nucleus, and nonzero values corresponding to a nucleus.
        """,
        centers="The list of centroids, one for each nuclear mask",
    ),
)
@dataclass(frozen=True, kw_only=True)
class NucleiVisualisationData:
    image: PixelArray
    masks: PixelArray
    centers: list[Tuple[NucleusNumber, ImagePoint2D]]

    def __post_init__(self) -> None:
        # First, handle the raw image.
        if len(self.image.shape) == 5:
            if self.image.shape[0] != 1:
                raise ValueError(
                    "5D image for nuclei visualisation must have trivial first"
                    f" dimension; got {self.image.shape[0]} (not 1)"
                )
            object.__setattr__(self, "image", self.image[0])
        if len(self.image.shape) == 4:
            if self.image.shape[0] == 1:
                logging.debug("Collapsing trivial channel axis for nuclei image")
                object.__setattr__(self, "image", self.image[0])
            else:
                logging.debug(
                    "Multiple channels in nuclei image; attempting to determine which"
                    " to use"
                )
                nuc_channel: int = determine_nuclei_channel()
                if nuc_channel >= self.image.shape[0]:
                    raise ValueError(
                        "Illegal nuclei channel value (from"
                        f" {LOOPTRACE_NAPARI_NUCLEI_CHANNEL_ENV_VAR}), {nuc_channel},"
                        f" for channel axis of length {self.image.shape[0]}"
                    )
                logging.debug(
                    "Using nuclei channel (from %s): %d",
                    LOOPTRACE_NAPARI_NUCLEI_CHANNEL_ENV_VAR,
                    nuc_channel,
                )
                object.__setattr__(self, "image", self.image[nuc_channel])
        if len(self.image.shape) == 3:
            if self.image.shape[0] == 1:
                logging.debug("Collapsing trivial z-axis for nuclei image")
                object.__setattr__(self, "image", self.image[0])
            else:
                logging.debug("Max projecting along z for nuclei image")
                object.__setattr__(self, "image", max_project_z(self.image))
        if len(self.image.shape) == 2:
            # All good
            pass
        else:
            raise ValueError(
                f"Cannot use image with {len(self.image.shape)} dimension(s) for nuclei"
                " visualisation"
            )

        # Then, handle the masks image.
        if len(self.masks.shape) == 5:
            if any(d != 1 for d in self.masks.shape[:3]):
                raise ValueError(
                    "5D nuclear masks image with at least 1 nontrivial (t, c, z) axis!"
                    f" {self.masks.shape}"
                )
            logging.debug("Reducing 5D nuclear masks to 2D")
            object.__setattr__(self, "masks", self.masks[0, 0, 0])
        if len(self.masks.shape) != 2:
            raise ValueError(
                f"Need 2D image for nuclear masks! Got {len(self.masks.shape)}:"
                f" {self.masks.shape}"
            )


def build_layers(
    bundles: Mapping[FieldOfViewFrom1, NucleiVisualisationData],
) -> Tuple[ImageLayer, MasksLayer, CentroidsLayer]:
    images = []
    masks = []
    nuclei_points = []
    nuclei_labels = []
    for i, (_, visdata) in enumerate(sorted(bundles.items(), key=itemgetter(0))):
        images.append(visdata.image)
        masks.append(visdata.masks)
        for nuc, pt in visdata.centers:
            nuclei_points.append([i, pt.get_y_coordinate(), pt.get_x_coordinate()])
            nuclei_labels.append(nuc.get)

    # Prep the data for presentation as layers.
    images: da.Array = da.stack(images)  # type: ignore[no-redef]
    logging.debug("Image layer data shape: %s", images.shape)  # type: ignore[attr-defined]
    masks: da.Array = da.stack(masks)  # type: ignore[no-redef]
    logging.debug("Masks layer data shape: %s", masks.shape)  # type: ignore[attr-defined]

    labs_text = {
        "string": "{nucleus}",
        "size": 10,  # tested on FOVs of 2048 (x) x 2044 (y), with ~15-20 nuclei per FOV
        "color": "black",
    }
    points_params = {
        "name": "labels",
        "size": 0,
        "text": labs_text,
        "properties": {"nucleus": nuclei_labels},
    }

    images_layer = (images, {"name": "max_proj_z"}, "image")
    masks_layer = (masks, {"name": "masks"}, "labels")
    points_layer = (nuclei_points, points_params, "points")
    return images_layer, masks_layer, points_layer  # type: ignore[return-value]


@doc(
    summary=(
        "Read (from environment variable) the image channel in which to find nuclei"
        " signal."
    ),
    raises=dict(
        ValueError="When the environment variable value's set to a non-integer-like",
    ),
    returns="The integer value of image channel in which to find nuclei signal",
)
def determine_nuclei_channel():
    nuc_channel = os.getenv(LOOPTRACE_NAPARI_NUCLEI_CHANNEL_ENV_VAR, "")
    if nuc_channel == "":
        raise ValueError(
            "When using nuclei images with multiple channels, nuclei channel must be"
            " specified through environment variable"
            f" {LOOPTRACE_NAPARI_NUCLEI_CHANNEL_ENV_VAR}."
        )
    try:
        nuc_channel: int = int(nuc_channel)  # type: ignore[no-redef]
    except TypeError as e:
        raise ValueError(
            "Illegal nuclei channel value (from"
            f" {LOOPTRACE_NAPARI_NUCLEI_CHANNEL_ENV_VAR}): {nuc_channel}"
        ) from e


@doc(
    summary=(
        "Directly in given folder, find all filepaths with given extension and a field"
        " of view embedded in filename"
    ),
    parameters=dict(
        folder="Path to folder in which to find files",
        extension="The extension of files to find",
    ),
    raises=dict(
        Exception="If the same FOV is found to correspond to more than one path"
    ),
    returns="Mapping from field of view to filepath",
    see_also=dict(
        get_fov_sort_key="The function used to try to parse FOV from filename"
    ),
)
def find_paths_by_fov(folder: Path, *, extension: str) -> Dict[FieldOfViewFrom1, Path]:
    image_paths = {}
    for fn in os.listdir(folder):
        fp = folder / fn
        fov = get_fov_sort_key(fp, extension=extension)
        if fov is not None:
            if fov in image_paths:
                raise RuntimeError(f"FOV {fov} already seen in folder! {folder}")
            image_paths[fov] = fp
    return image_paths


@doc(
    summary="Get the sort key (by FOV) for the given filename or filepath.",
    parameters=dict(
        path="The path for which to get the FOV (to be used as sort key)",
        extension="The expected extension of the file name or path",
    ),
    raises=dict(
        TypeError="If the given value is neither a path nor a string",
    ),
    returns="Field of view parsed from filename, if parse succeeded; otherwise, None",
)
def get_fov_sort_key(path: PathLike, *, extension: str) -> Optional[FieldOfViewFrom1]:
    if not isinstance(path, (str, Path)):
        raise TypeError(
            f"Cannot parse sort-by-FOV key for {extension} stack from alleged path:"
            f" {path} (type {type(path).__name__})"
        )
    _, fn = os.path.split(path)
    if not (fn.startswith("P") and fn.endswith(extension)):
        return None
    rawval: str = fn.lstrip("P").rstrip(extension)
    if rawval.endswith(extension):
        # Support older looptrace-emitted data.
        warnings.warn(
            f"Stripping second '{extension}' extension; use data from newer software",
            DeprecationWarning,
        )
        rawval = rawval.rstrip(extension)
    try:
        rawval: int = int(rawval)  # type: ignore[no-redef]
    except ValueError:
        return None
    return FieldOfViewFrom1(rawval)  # type: ignore[arg-type]


@doc(
    summary=(
        "Max project images z-stack along the z-axis, assumed to be axis 0 (first"
        " axis)."
    ),
    parameters=dict(img="The image stack to max-project along z"),
    raises=dict(ValueError="If the given image isn't 3D (z-stack of 2D images)"),
)
def max_project_z(img: PixelArray) -> PixelArray:
    if len(img.shape) != 3:
        raise ValueError(
            f"Image to max-z-project must have 3 dimensions! Got {len(img.shape)}"
        )
    return da.max(img, axis=0)


class ZarrParseException(Exception):
    def __init__(self, *, path: Path, msg: str) -> None:
        super().__init__(f"Parsing {path} failed with message: {msg}")
        self.path = path


def _read_csv(fp: Path) -> list[Tuple[NucleusNumber, ImagePoint2D]]:
    logging.debug("Reading CSV: %s", fp)
    df = pd.read_csv(fp, index_col=0)
    nuclei = df[
        "label"
    ]  # preserves data type of this column / field, .iterrows() seems to lose it.
    ys = df["yc"]
    xs = df["xc"]
    return [
        (NucleusNumber(n), ImagePoint2D(y=y, x=x)) for n, y, x in zip(nuclei, ys, xs)
    ]


def _read_zarr(root: Path) -> PixelArray:
    logging.debug("Reading ZARR: %s", root)
    if (root / ".zarray").is_file():
        data_root = root
    elif (root / "0" / ".zarray").is_file():
        data_root = root / "0"
    else:
        raise ZarrParseException(
            path=root, msg="Failed to find .zarray to indicate data folder"
        )
    return zarr.open(data_root)[:]
